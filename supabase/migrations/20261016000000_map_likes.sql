-- Public visitors can read and submit map ratings through two narrow RPCs.
-- The table and the privileged implementation live outside the exposed API schema.
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists private.map_likes (
  id bigint generated always as identity primary key,
  voter_id uuid not null unique,
  nickname text not null check (char_length(nickname) between 1 and 24),
  rating integer not null check (rating in (0, 1)),
  created_at timestamptz not null default now()
);
revoke all on private.map_likes from public, anon, authenticated;
alter table private.map_likes enable row level security;

create or replace function private.get_map_likes()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select pg_catalog.jsonb_build_object(
    'count', (select pg_catalog.count(*) from private.map_likes),
    'love_count', (select pg_catalog.count(*) from private.map_likes where rating = 1),
    'broken_heart_count', (select pg_catalog.count(*) from private.map_likes where rating = 0),
    'likes', coalesce(
      (
        select pg_catalog.jsonb_agg(
          pg_catalog.jsonb_build_object(
            'nickname', nickname,
            'rating', rating,
            'created_at', created_at
          ) order by id desc
        )
        from (
          select id, nickname, rating, created_at
          from private.map_likes
          order by id desc
          limit 100
        ) as recent
      ),
      '[]'::jsonb
    )
  );
$$;

create or replace function private.submit_map_like(
  p_nickname text,
  p_rating integer,
  p_voter_id uuid,
  p_website text default ''
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  cleaned_nickname text := pg_catalog.btrim(
    pg_catalog.regexp_replace(coalesce(p_nickname, ''), '[[:cntrl:]]', '', 'g')
  );
begin
  if pg_catalog.char_length(cleaned_nickname) not between 1 and 24
     or p_rating is null or p_rating not in (0, 1)
     or p_voter_id is null
     or pg_catalog.btrim(coalesce(p_website, '')) <> '' then
    raise exception 'Invalid map rating' using errcode = '22023';
  end if;

  insert into private.map_likes (voter_id, nickname, rating)
  values (p_voter_id, cleaned_nickname, p_rating)
  on conflict (voter_id) do update
    set nickname = excluded.nickname,
        rating = excluded.rating,
        created_at = pg_catalog.now();

  return private.get_map_likes();
end;
$$;

-- PostgREST exposes public RPCs; these invoker wrappers delegate to the
-- restricted private functions without exposing the table or voter IDs.
create or replace function public.get_map_likes()
returns jsonb
language sql
stable
security invoker
set search_path = ''
as $$ select private.get_map_likes(); $$;

create or replace function public.submit_map_like(
  p_nickname text,
  p_rating integer,
  p_voter_id uuid,
  p_website text default ''
)
returns jsonb
language sql
volatile
security invoker
set search_path = ''
as $$ select private.submit_map_like(p_nickname, p_rating, p_voter_id, p_website); $$;

revoke execute on function private.get_map_likes() from public, anon, authenticated;
revoke execute on function private.submit_map_like(text, integer, uuid, text) from public, anon, authenticated;
revoke execute on function public.get_map_likes() from public, anon, authenticated;
revoke execute on function public.submit_map_like(text, integer, uuid, text) from public, anon, authenticated;
grant usage on schema private to anon;
grant execute on function private.get_map_likes() to anon;
grant execute on function private.submit_map_like(text, integer, uuid, text) to anon;
grant execute on function public.get_map_likes() to anon;
grant execute on function public.submit_map_like(text, integer, uuid, text) to anon;
