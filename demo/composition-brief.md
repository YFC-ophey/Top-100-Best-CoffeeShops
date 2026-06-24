# Hyperframes Composition Brief: ROAST.

## Objective
Create a short launch-style brag video for ROAST., an interactive world-map explorer for *The World's 100 Best Coffee Shops*.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 20 seconds

## Source Material
- Project root: `Top-100-Best-CoffeeShops/` (cloned for this run)
- Primary files read: `templates/index.html` (inline `<style>` + markup + JS), `README.md`, `data/current_list.json`
- Product name: ROAST. (wordmark renders the trailing period in brand orange)
- Tagline / strongest claim: "Wherever the coffee vibes hit, open ROAST. and instantly see if one of the world's best coffee shops is near you."
- Key UI or visual moment to recreate: the dark glassmorphism map panel with glowing orange country-density bubbles + pulsing individual shop markers, and the right-hand shop detail card with the `#1 Top 100` rank badge and Get Directions button.
- Copy that must appear verbatim:
  - "Is one of the world's best coffee shops near you?"
  - "200 shops · 56 countries"
  - "#1 Top 100 · Onyx Coffee Lab"
  - "Free. No API key. Auto-updated every February."
  - "Wherever the coffee vibes hit."
  - "yfc-ophey.github.io/Top-100-Best-CoffeeShops"

## Creative Direction
- Tone preset: default
- Creative direction: playful, good-vibes coffee-lover map reveal — warm and postable, café-at-golden-hour energy without the corporate polish
- Interpretation: comfortable pacing with room to breathe (4-5 scenes); friendly conversational copy; clean crossfade/wipe transitions and lively motion. Warm and fun, not premium-restrained — but still clean, never chaotic.
- Angle: A playful good-vibes reveal built on the founder's real promise — wherever the coffee vibes hit, ROAST. finds the nearest world-class shop. Specificity comes from real numbers (200 shops, 56 countries, 2 lists), the real #1 (Onyx Coffee Lab), and the actual dark-roast UI. A happy little flex lands at the end: it's free and refreshes itself every February.
- Hook: espresso-dark screen, gold coffee-bean icon glows on, then "Is one of the world's best coffee shops near you?" slams in and holds.
- Outro / punchline: "Free. No API key. Auto-updated every February." resolving to the ROAST. wordmark + tagline + URL.
- Avoid:
  - Generic SaaS language ("streamline your coffee journey")
  - Abstract filler visuals / particle fields / color washes
  - Any redesign of the brand — use the project's real dark-roast palette and fonts

## Visual Identity
- Background: `#130a08` espresso dark; real treatment is radial orange `rgba(223,110,46,0.22)` + gold `rgba(247,198,154,0.14)` glows over `linear-gradient(158deg, #080403, #130a08 40%, #21120d)`
- Text: `#f8efe6` warm white; muted `#b8a08f`
- Accent: `#df6e2e` brand orange; `#f7c69a` gold for highlights/badges
- Display font: Cabinet Grotesk (700/800) — fallback to a strong geometric sans if unavailable
- Body font: General Sans (400-600) — fallback to system sans
- Visual references from the project: glassmorphism panels (`rgba(31,18,14,0.86)` + `blur(16px)`, border `rgba(247,198,154,0.2)`); orange country bubbles + warm-white shop dots; the `pulse-ring` marker animation; the `#1 Top 100` orange rank badge; the bright orange "Get Directions" primary button; Collection / Country / Rank Band filter chips.

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Hook — 3s — gold bean icon, then "Is one of the world's best coffee shops near you?" holds
2. The map ignites — 4s — orange country bubbles pop in by continent; counter settles on "200 shops · 56 countries · 2 lists"
3. Tap a country — 4s — cursor taps the Peru (28 shops) bubble; map zooms; shop markers pulse in
4. Shop detail — 4s — glass detail panel slides in: hero photo, "#1 Top 100 · Onyx Coffee Lab" badge, Get Directions button, filter chips
5. Outro — 5s — "Free." / "No API key." / "Auto-updated every February." then ROAST. wordmark + "Wherever the coffee vibes hit." + URL

## Audio
- Audio role: warm bed — gentle, premium, café-at-golden-hour
- Audio arc: low under the hook, opens up as the map ignites and the flow plays, soft fade-out under the outro card
- Music: `happy-beats-business-moves-vol-9-by-ende-dot-app.mp3` (~115 BPM)
- Music treatment: start 0s at moderate-low volume, swell slightly through Scenes 2-4, fade out under the Scene 5 logo
- Music cue guidance: bundled preset at `~/.claude/skills/brag/assets/music/cues/happy-beats-business-moves-vol-9-by-ende-dot-app.music-cues.json`. Strong cues to consider locking: 4.23s & 6.34s (map/bubble ignition), 10.54s (country-tap zoom), 12.65s (detail-panel slide-in). Beat grid ~0.52s spacing for bubble pop sequence.
- Audio-reactive treatment: subtle — drive map glow / bubble breathing from RMS+bass; no waveform or equalizer visuals
- Audio-coupled moments:
  - Scene 1 — soft pop as the bean icon lands
  - Scene 2 — beat-grid UI pops on continent bubble groups; tick on the count-up
  - Scene 3 — interface click on the Peru tap; soft swell as markers pulse
  - Scene 4 — slide whoosh on the panel; soft chime when the #1 badge settles
  - Scene 5 — soft tick per claim line; music fade under the logo lockup
- SFX selection guidance: sparse and motion-matched. UI/interface pops for bubbles, a clean click for the tap, a soft slide for the panel, one gentle chime for the badge. Nothing loud or comedic.
- SFX analysis guidance: use `~/.claude/skills/brag/assets/sfx/sfx-analysis.md` (+ `.json`); prefer low high-frequency-risk files for the repeated bubble pops.
- Exact SFX choice: Hyperframes chooses filenames, timestamps, density, and volume from the implemented animation.
- Audio files: copy chosen music + SFX into `brag-output/composition/assets/`. (Music already staged at `brag-output/composition/assets/music/`.)

## Hyperframes Instructions
Use the current `hyperframes` skill and CLI workflow. Prefer native Hyperframes conventions over anything in `/brag`.

Requirements:
- Show at least one real UI element from the project (the map panel and the shop detail card both qualify — use both).
- Keep all text readable: hook line holds ≥1.5s; the three outro claim lines hold ~0.8s each.
- Keep the video within 15-25s (target 20s).
- Include the music/SFX layer; treat the audio notes as guidance, choose SFX after the visuals exist.
- Lock 1-3 major tweens to the strong cues above (±0.15s); snap the bubble sequence to consecutive beats (±0.10s).
- Wire at least one visual element to the audio data (subtle), or document if ffmpeg/extraction is unavailable.
- Run `npx hyperframes lint` (zero errors) and validate before rendering.
