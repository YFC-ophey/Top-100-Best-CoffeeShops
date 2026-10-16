import sqlite3
import uuid

from fastapi.testclient import TestClient

from src.web_app import create_app


def _client(tmp_path):
    app = create_app(
        data_file=tmp_path / "data" / "current_list.json",
        csv_file=tmp_path / "output" / "coffee_shops.csv",
        kml_file=tmp_path / "output" / "coffee_shops.kml",
        likes_db_path=tmp_path / "likes.sqlite3",
    )
    return TestClient(app)


def test_likes_api_starts_empty_and_publishes_ratings(tmp_path):
    client = _client(tmp_path)

    empty = client.get("/api/likes")
    assert empty.status_code == 200
    assert empty.json() == {"count": 0, "love_count": 0, "broken_heart_count": 0, "likes": []}

    love = client.post(
        "/api/likes",
        json={"nickname": "  Café Fan  ", "rating": 1, "voter_id": str(uuid.uuid4())},
    )

    assert love.status_code == 201
    assert love.json()["count"] == 1
    assert love.json()["love_count"] == 1
    assert love.json()["broken_heart_count"] == 0
    assert love.json()["likes"][0]["nickname"] == "Café Fan"
    assert love.json()["likes"][0]["rating"] == 1
    assert love.json()["likes"][0]["created_at"].endswith("Z")

    broken = client.post(
        "/api/likes",
        json={"nickname": "Needs more work", "rating": 0, "voter_id": str(uuid.uuid4())},
    )
    assert broken.status_code == 201
    assert broken.json()["count"] == 2
    assert broken.json()["love_count"] == 1
    assert broken.json()["broken_heart_count"] == 1


def test_one_current_rating_per_browser_can_be_updated_and_nickname_is_text(tmp_path):
    client = _client(tmp_path)
    voter_id = str(uuid.uuid4())
    payload = {"nickname": "<img src=x>", "rating": 1, "voter_id": voter_id}

    first = client.post("/api/likes", json=payload)
    assert first.status_code == 201
    assert first.json()["likes"][0]["nickname"] == "<img src=x>"
    payload.update({"nickname": "Updated name", "rating": 0})
    updated = client.post("/api/likes", json=payload)
    assert updated.status_code == 201
    assert updated.json()["count"] == 1
    assert updated.json()["love_count"] == 0
    assert updated.json()["broken_heart_count"] == 1
    assert updated.json()["likes"][0]["nickname"] == "Updated name"
    assert updated.json()["likes"][0]["rating"] == 0


def test_likes_api_rejects_invalid_ratings_names_and_honeypot(tmp_path):
    client = _client(tmp_path)
    voter_id = str(uuid.uuid4())

    assert client.post("/api/likes", json={"nickname": "Cafe Fan", "rating": 2, "voter_id": voter_id}).status_code == 422
    assert client.post("/api/likes", json={"nickname": "Cafe Fan", "rating": 5, "voter_id": str(uuid.uuid4())}).status_code == 422
    assert client.post("/api/likes", json={"nickname": "   ", "rating": 1, "voter_id": str(uuid.uuid4())}).status_code == 422
    assert client.post("/api/likes", json={"nickname": "Cafe Fan", "rating": 1, "voter_id": str(uuid.uuid4()), "website": "bot"}).status_code == 422
    assert client.get("/api/likes").json()["count"] == 0


def test_old_five_point_ratings_migrate_to_binary_sentiment(tmp_path):
    database = tmp_path / "likes.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE map_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voter_id TEXT NOT NULL UNIQUE,
                nickname TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )"""
        )
        connection.executemany(
            "INSERT INTO map_likes (voter_id, nickname, rating) VALUES (?, ?, ?)",
            [(str(uuid.uuid4()), "Old love", 5), (str(uuid.uuid4()), "Old feedback", 2)],
        )

    response = _client(tmp_path).get("/api/likes")
    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert response.json()["love_count"] == 1
    assert response.json()["broken_heart_count"] == 1
    assert {row["rating"] for row in response.json()["likes"]} == {0, 1}


def test_likes_subpage_renders_public_nickname_notice(tmp_path):
    response = _client(tmp_path).get("/likes")

    assert response.status_code == 200
    assert "Latest love notes" in response.text
    assert "Nicknames are shared here" in response.text
    assert "❤️ or 💔" in response.text
    assert "love-votes" in response.text
    assert "window.location.origin" in response.text


def test_likes_api_sets_configured_cors_origin(tmp_path, monkeypatch):
    monkeypatch.setenv("LIKES_ALLOWED_ORIGINS", "https://yfc-ophey.github.io")
    client = _client(tmp_path)

    response = client.options(
        "/api/likes",
        headers={
            "Origin": "https://yfc-ophey.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://yfc-ophey.github.io"
    )
