# Profile setup

Everything you edit lives in `profile.json`. The renderer in `profilekit/` turns it into one SVG, served two ways:

| Path | What it is | Telemetry |
|---|---|---|
| `profile.svg` | Static snapshot, rebuilt by the Action on every push to the config | GitHub stats at build time, no access counter |
| `https://YOUR-PROJECT.vercel.app/live.svg` | Live endpoint (`api/profile.py`) | Counted and refreshed on **every** profile view |

## Why a live endpoint

A file committed to the repo can't change when someone opens your profile, and Actions can't run on page views. So the live version is a tiny Python function: every time GitHub's image proxy (camo) fetches the image, it increments the access counter, reads the previous visit time, pulls fresh GitHub stats and renders. It sends `no-cache` headers so GitHub fetches it again on each view instead of reusing a copy.

## 1. Deploy the live endpoint (Vercel, free tier)

1. Push this folder to your `absolute-ctrl/absolute-ctrl` repo.
2. On vercel.com: **Add New → Project → Import** that repo. Framework preset: **Other**. No build command. Deploy.
3. **Storage → Create → Upstash for Redis** (Marketplace), connect it to the project. It injects the REST URL and token as env vars (`KV_REST_API_URL`/`KV_REST_API_TOKEN` or `UPSTASH_REDIS_REST_URL`/`UPSTASH_REDIS_REST_TOKEN`; both work).
4. **Settings → Environment Variables**: add `GH_TOKEN` = a fine-grained GitHub token with *Public repositories (read-only)* access. No extra permissions needed.
5. Redeploy, then open `https://YOUR-PROJECT.vercel.app/live.svg?nocount=1` in a browser to check it.

## 2. Point the README at it

In `README.md`, change `src="profile.svg"` to `src="https://YOUR-PROJECT.vercel.app/live.svg"`.
Vercel redeploys on every push, so edits to `profile.json` go live within about a minute.

Notes:
- `?nocount=1` renders without counting, useful while you tweak things.
- Counts include every fetch of the image, so bots and your own visits count too.
- Without Redis the profile still renders; the counter shows `--`. Without `GH_TOKEN` the stats show `no link`.
- `telemetry.stats_cache_seconds` is `0` (fresh GitHub stats on every view). If loads ever feel slow, set it to `60`; the access counter still updates on every view regardless.

## Local preview

```
python scripts/build.py          # writes profile.svg
```
Open `profile.svg` in a browser to watch the animations. `GH_TOKEN=... python scripts/build.py` includes real stats.

---

## profile.json reference

### Colors
- `theme`: name of an entry in `palettes`. Ships with `phosphor`, `amber`, `ice`, `paper`.
- `palettes.<name>`: 8 colors.
  - `background`: CRT background
  - `panel`: cartridge body
  - `screen`: inside the little screens, also used as the terrain fill and crack ink
  - `primary`: main text/phosphor
  - `accent`: highlights, headers
  - `dim`: borders, secondary text
  - `shade`: dark faces (voxel sides, terminal header bar)
  - `glow`: the radial glow at the top
- `palette_overrides`: tweak individual colors without editing a palette, e.g. `{ "accent": "#FF5CA8" }`.

### Text
`boot`, `whoami`, `mission`, `footer`, and the `telemetry.labels` are all plain text. Line counts can grow or shrink; sections resize.

### Specs table
`specs.rows` is a list of `[language, graphics/platform, toolchain]`. Any empty string renders `specs.placeholder` dimmed. The third row ships empty; fill it in to activate it, e.g. `["Rust", "wgpu", "cargo"]`. You can add more rows too.

### Projects
Each entry in `programs.slots`:
- `id`: slot letter shown on the card
- `title`, `stack`: card text
- `status`: any key from `statuses`
- `art`: `terrain`, `terminal`, `voxels`, `engine` or `idle`

Slot count is free (cards flow two per row). The header's "N slots, M in use" is computed.

`statuses.<NAME>`:
- `color`: palette key for the card border and badge
- `in_use`: counts toward "in use"; `false` dims the card text
- `blink`: makes the badge blink

Add your own statuses freely, e.g. `"ARCHIVED": { "color": "dim", "in_use": false, "blink": false }`.

### Animation settings (`art`)
- `terrain.loop_seconds`, `terrain.rows`: speed and density of the flyover (more rows = bigger file)
- `terminal.header`, `terminal.columns`, `terminal.step_seconds`: scroll speed per record
- `voxels.loop_seconds`: one mine-and-place cycle
- `engine.loop_seconds`, `engine.nodes` (5 names), `engine.command`, `engine.shaders`, `engine.triangle_colors` (3 hex values or palette keys), `engine.triangle_subdivisions`
- `idle.label`

### Telemetry
- `telemetry.fields`: which lines appear, and in what order: `accesses`, `previous_access`, `repos`, `stars`, `commits`, `prs`, `followers`
- `telemetry.languages_shown`: bars in the language mix
