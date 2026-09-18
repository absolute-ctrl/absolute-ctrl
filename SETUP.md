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

### How it plays: the sequence (`animation`)

Everything on the screen is printed in order, like a real terminal session: one thing appears, then the next, and nothing starts before the thing before it has finished. Text lands whole and instantly; only three kinds of thing are deliberately slow -- progress bars, the mission meters and the language bars (which fill one block at a time), and the command lines you "type" (`boot.prompt`, `whoami.command`), which arrive character by character.

- `enabled`: `false` renders the finished screen with no animation at all. Useful for a screenshot.
- `speed`: the one knob worth touching. `1.0` is the authored pace, `1.5` is 50% faster, `0.7` slower. It scales every timing below, so the order never changes.
- `start_delay`: dead time before the first line appears.
- `line_seconds`: pause after one printed line.
- `chunk_seconds`: pause after a block that appears at once (a header, a table frame, a card shell).
- `section_seconds`: extra pause between sections.
- `pause_seconds`: the "thinking" beat between a label and its result, e.g. between `Memory test ....` and `640K OK`.
- `block_seconds`: per block when a meter or a bar fills.
- `bar_seconds`: default progress-bar fill time.
- `card_seconds`, `card_load_seconds`: the beat between the parts of a program card, and how long its screen shows `LOADING` before the art appears. Set `card_load_seconds` to `0` to skip the loading bar.
- `typing.enabled`: `false` makes typed lines appear whole like everything else.
- `typing.chars_per_second`, `typing.cursor`, `typing.blink_seconds`: typing speed, whether a cursor follows the caret, and how fast it blinks.
- `logo.row_seconds`, `logo.bar_seconds`: how fast the splash logo prints -- one mosaic row, and its fill bar. The splash's *pauses* live in the `logo` block and are not scaled by `speed`.

The whole run currently lasts about 15 seconds. It plays once and freezes on the finished screen; loops (the cartridge art, blinking cursors) keep running after that.

### Manufacturer splash (`logo`)

The screen that plays *before* the BIOS, like a hardware vendor logo. It is an overlay across the whole image rather than a section, so when it leaves it takes its space with it and the profile starts at the top. Delete the whole `logo` block, or set `"enabled": false`, and the profile starts at the BIOS instead. (With `animation.enabled: false` there is no boot screen at all -- a still frame can't have one.)

It runs in phases, and these five are **wall-clock seconds**: `animation.speed` does not scale them, because a five-second hold is meant to be five seconds.

- `black_seconds`: pure black before the tube does anything.
- `warmup_seconds`: the black fading off, so the phosphor glow comes up like a CRT warming.
- `warm_hold_seconds`: glow alone, nothing on it.
- `hold_seconds`: how long the finished logo stays before it is cleared.
- `blank_seconds`: black again, with nothing but a waiting cursor, before the BIOS takes over.
- `black`: the colour of the first phase; `cursor_x` / `cursor_y`: where the waiting cursor sits.

How fast the logo *prints* is still in `animation.logo` (`row_seconds` per mosaic row, `bar_seconds` for the fill bar), because that is printing speed, not a pause.


- `enabled`: on/off.
- `top_left`, `top_right`: the small model/firmware lines at the top.
- `name`, `name_spacing`, `tagline`: the big brand text under the logo.
- `bar`, `bar_label`, `bar_width`, `bar_blocks`: the fill bar. It shows a percentage as it fills.
- `lines`: the small centred lines at the bottom.
- `frame`: the thin box drawn around the splash.

`logo.art` is the picture itself, printed row by row in characters:

- `mode`: `"ascii"` turns an image into a character mosaic (this is the helmet); `"image"` draws the picture itself, tinted like a slot image; `"none"` leaves just the text.
- `src`: the image. **`"ascii"` needs a PNG** (8-bit, non-interlaced -- anything an editor exports), because the mosaic is decoded without any third-party library. Use `"image"` mode for JPEG. If the file can't be read, the splash says so instead of breaking.
- `columns`: how many characters wide. More columns = more detail and a bigger file.
- `cell_width`, `row_height`: the size of one character cell in pixels. Together with `columns` these set how big the logo is; row count follows from the image's aspect ratio.
- `font_scale`: glyph size relative to a cell. Below `1.0` leaves air between characters.
- `ramp`: the characters used, from emptiest to densest. `" .:-=+*#%@"` by default; `" .:oO0@"` or block characters also work.
- `threshold`: below this much ink a cell is left blank (the page around the helmet).
- `invert`: `true` for art that is light on a dark background.
- `gamma`, `saturation`, `dark_level`, `bright_level`: how cells are sorted into three classes -- `dark` (the black visor), `mid` (the body) and `bright` (the gold trim). `saturation` is how colourful a cell must be to count as trim; the two levels are luminance cuts.
- `colors`: the palette colour for each class.
- `density`: how much ink each class gets. Lowering `dark` makes the visor a faint stipple; raising it makes it a solid slab.

For `"image"` mode, `width` and `height` set the box it is fitted into, and every slot-image setting (`crop`, `fit`, `zoom`, `align`, `opacity`, `contrast`, `levels`, `shadow`/`midtone`/`highlight`, ...) works the same way.

### Closing login screen (`login`)

The last thing on the image: the helmet again, and a login prompt that never gets answered. It is a normal section at the bottom, so it prints after the footer and stays on screen. Set `"enabled": false` (or remove the block) to end at `READY.` as before.

- `top_left`, `top_right`, `name`, `name_spacing`, `tagline`, `lines`, `art`: exactly the same keys as `logo`, and `art` takes the same mosaic settings (the default uses a smaller grid than the splash).
- `name_size`: the brand size here, smaller than the splash by default.
- `title`: the line above the box.
- `box_width` and `fields`: the prompt box. Each field is `{ "label": ..., "value": ..., "cursor": true|false }`. A field with a `value` is *typed out*; a field with an empty value just shows its label and, with `"cursor": true`, a cursor that blinks forever. That is what makes it read as waiting for a password.
- `footer_lines`: small centred lines under the box.

### Cutting a slot image out of its rectangle (`image.cutout`)

A photo is a rectangle, and on a near-black screen its own background shows as a visible box. `cutout` keys the picture on its brightness so the dark background becomes transparent and only the subject is left sitting on the phosphor. Size, position and colour are untouched -- it only changes alpha.

- `enabled`: on/off.
- `low`: brightness at or below which the picture is fully transparent.
- `high`: brightness at or above which it is fully opaque. Between the two it ramps.
- `gamma`: bends that ramp; above `1` holds the mid-tones back longer.
- `floor` / `ceiling`: the alpha at the two ends. `floor: 0.08` leaves a ghost of the background instead of cutting it completely.

Raise `low` to strip more background; lower it to keep dark clothing and hair. Keep a `fade_edges` of about `0.25` as well: with the background already cut away it no longer draws a box, it just dissolves the places where the subject runs into the edge of the crop, which is the last thing that would read as a rectangle.

### Making a slot image a ghost (`image.glow`)

A bloom pass: a blurred copy of the picture with only a faint sharp copy left on top of it, so the subject reads as something glowing behind the glass rather than a photograph pinned to the screen. Pair it with a low `opacity` and `levels: 0` (no posterising, so there are no hard bands to give the edges away).

- `enabled`: on/off.
- `radius`: how far the halo spreads. `2` is a soft edge, `6` is barely there.
- `halo`: brightness of the blurred copy. Above `1` makes the glow stronger than the original.
- `core`: how much of the sharp picture survives on top. `0.5` still reads as a face; `0.15` is a haunting.

The shipped slots use `radius: 1.2`, `halo: 0.45`, `core: 0.88` at `opacity: 0.5`: sharp, with just enough bloom to look like phosphor rather than a photograph. `halo` and `core` trade off against each other, so to change the softness without changing how bright the picture reads, move them in opposite directions -- `radius: 4`, `halo: 1.05`, `core: 0.26` is the same brightness, fully out of focus. `cutout.low` is the other half of the dial -- raising it eats more of the dark parts, which is why Ritchie (mostly dark sweater) is keyed lower than Thompson.

### A brighter core on the face (`image.hotspot`)

A second pass of the same picture, masked to a soft circle, so the face is the brightest thing on the screen and the light drops off with distance from it. It draws the picture again rather than washing colour over it, which means the extra light only lands where the subject is -- the background stays exactly as transparent as it was, and no disc appears around him.

- `enabled`: on/off.
- `center`: `[x, y]` from `0` to `1` within the picture, where the light is strongest. `[0.5, 0.40]` is roughly eye level.
- `radius`: how far the bright core reaches, as a fraction of the picture.
- `inner`: how much of the core stays at full strength before it starts dropping (`0` starts falling immediately).
- `strength`: how much the second pass adds, `0` to `1`. The shipped slots use `0.5`.

This stacks on top of `opacity` (the overall level) and the `fade_shape: "radial"` falloff (which dims the outside). Together they read as one light source at the face: `strength` controls how hot the middle gets, `fade_radius` how quickly everything outside it dies away.

### Drifting static (`art.idle`)

- `noise_fields`: how many complete speckle fields are cycled. `1` is the old frozen grain; `3` makes the static drift without animating every dot.
- `noise_seconds`: how long one full cycle through the fields takes. Longer is calmer.
- `band_seconds`: how long the rolling band takes to sweep down the screen.
- `label`: the `NO SIGNAL` text.

### Layout, effects and sizes

`layout`: `width` (whole screen), `margin`, `card_columns` (cards per row), `card_gap`, `card_row_gap`, `section_gap`, `corner_radius`, `border`. Cards themselves stay 400x290, because the cartridge art is drawn for exactly that box.

`effects`: `scanlines` and their `scanline_opacity` / `scanline_spacing`, `glow` (the halo at the top), `blur` (the phosphor bloom; `0` for a crisp screen), `dividers` (the double rules between sections), `flicker` (`0` off, up to `0.3` for a CRT that can't hold a picture).

`sizes`: font size of every kind of text -- `header`, `body`, `small`, `note`, `tagline`, `boot`, `boot_name`, `logo_name`, `table`, `table_header`, `meter`, `card_slot`, `card_status`, `card_title`, `card_stack`, `telemetry`, `footer`.

### Text
`boot`, `whoami`, `mission`, `footer`, and the `telemetry.labels` are all plain text. Line counts can grow or shrink; sections resize.

Each entry in `boot.lines` is either a `[left, right]` pair, or an object for more control:

```json
{ "left": "Memory test ................ ", "right": "640K OK", "bar": true, "pause": 0.4 }
```

`bar` puts a small bar that fills between the label and the result (`boot.bar_width`, `boot.bar_blocks`, `boot.bar_seconds` control every such bar), and `pause` overrides how long the machine "thinks" before answering. `boot.prompt` is split at the `>`: what follows is typed out.

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

### Slot images (`programs.slots[].image`)
Any slot can have an image on its screen, drawn **under** that slot's animation and text. It's meant for the `idle` slots: the static, rolling band and label sit on top of it. Delete the `image` block, or set `"enabled": false`, and the slot goes back to the plain animated static.

Put the file in `assets/` and point `src` at it (PNG, JPEG, GIF or WebP). It's embedded in the SVG, because GitHub blocks images an SVG tries to load from elsewhere. Keep it small, ideally under about 150 KB. A slot image the same size as a small thumbnail is plenty for this screen. If two slots use the same file, it's embedded only once.

- `treatment`
  - `"theme"`: converted to grayscale, contrast-boosted, posterized and tinted with palette colors. Changing `theme` re-tints it automatically.
  - `"none"`: placed as is, for images you've already edited. `opacity`, `fade_edges` and the crop/fit settings still apply.
- `crop`: `[x, y, width, height]` as fractions of the image. `[0, 0, 0.5, 1]` is the left half.
- `fit`: `"contain"` shows the whole crop; `"cover"` fills the screen and trims the overflow.
- `zoom`: extra scale after fitting. `1.25` is 25% larger.
- `align`: `[x, y]` from `0` (left/top) to `1` (right/bottom), where the image sits on the screen.
- `opacity`: how dim it is overall.
- `fade_edges`: how softly the edges blend into the screen (`0` for hard edges, up to `0.45`). Used by the default `"box"` shape, which fades each side independently.
- `fade_shape`: `"box"` fades the four sides; `"radial"` makes one pool of light instead -- full strength around the middle, falling away evenly in every direction, so there are no corners and nothing marks where the picture ends. The shipped slots use `"radial"`.
  - `fade_inner`: how much of the middle stays at full strength before the falloff starts (`0` starts fading immediately, `0.4` keeps a wide bright core).
  - `fade_center`: `[x, y]` from `0` to `1`, where the brightest point sits. `[0.5, 0.44]` puts it on the face rather than the chest.
  - `fade_radius`: how far the light reaches, as a fraction of the picture. Smaller pulls everything into a tighter pool; larger lets it spread to the edges before dying.
- Tone settings, used only with `"theme"`:
  - `contrast`, `brightness`: before tinting. `brightness` goes from about `-0.5` to `0.5`.
  - `levels`: number of posterize steps. `0` gives a smooth tint.
  - `shadow`, `midtone`, `highlight`: the three colors the dark, mid and light tones map to. Palette keys or hex values.
- `pixelated`: `true` for chunky pixels when a small image is scaled up.
- `noise`: how much static is drawn over it (`0` to `1`).
- `label_position`: `"center"`, `"left"`, `"right"`, `"top"`, `"bottom"`, `"bottom-right"` or `"none"`.
- `label`: optional text replacing `art.idle.label` for this slot. `""` hides the box.

The defaults split `assets/homage.jpg` across E (left half) and F (right half). To show the full photo in one slot, use `"crop": [0, 0, 1, 1]`.

### Cartridge art (`art`)
- `terrain.loop_seconds`, `terrain.rows`: speed and density of the flyover (more rows = bigger file)
- `terminal.header`, `terminal.columns`, `terminal.step_seconds`: scroll speed per record
- `voxels.loop_seconds`: one mine-and-place cycle
- `engine.loop_seconds`, `engine.nodes` (5 names), `engine.command`, `engine.shaders`, `engine.triangle_colors` (3 hex values or palette keys), `engine.triangle_subdivisions`
- `idle.label`

### Telemetry
- `telemetry.fields`: which lines appear, and in what order: `accesses`, `previous_access`, `repos`, `stars`, `commits`, `prs`, `followers`
- `telemetry.languages_shown`: bars in the language mix
- `telemetry.leader_width`, `languages_x`, `language_bar_x`, `language_blocks`: dotted-leader width and where the language block bars sit
- `telemetry.live_label`, `snapshot_label`, `time_format`, `no_link_text`, `no_languages_text`: the wording in the header and in place of missing data
