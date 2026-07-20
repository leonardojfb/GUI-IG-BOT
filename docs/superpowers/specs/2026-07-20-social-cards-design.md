# Social Cards Generator — Instagram Automation Pro v7

**Date:** 2026-07-20
**Status:** Approved (design). Ready for implementation plan.
**App:** `Método IG VIDEOS v2.0/gui_premium_v7.py` (CustomTkinter) + new `social_cards.py`

## Goal

Add a feature that generates fake social-media post screenshots (Reddit, Twitter/X,
Instagram/Threads) with the user's own video frame or image composited inside the post's
media slot. Each generated card fills the platform's chrome (username, upvote/like/comment
counts, timestamps, verified badge, etc.) with plausible randomized — or manually pinned —
values. Output is a PNG per card; a card-intro video is a later stretch goal.

This is inspired by OOPSIE's Reddit/X/IG post generators, but the templates are rebuilt
from scratch by referencing the *real platforms'* public UI — not extracted from OOPSIE's
compiled binary or assets.

### Why (two stacked purposes)

1. **Ad-creative hook.** "Someone found this and posted it" framing reads as organic, not
   sponsored — higher CTR than a raw clip.
2. **Spoofing variance, one layer up.** The same underlying media wrapped in different fake
   platform chrome + randomized fields per copy produces visually distinct output per copy,
   on top of (not instead of) the existing FORGE pixel/EXIF spoofing — harder to
   duplicate-match across postings.

## Hard constraints

- **Standalone feature.** Lives on its own screen; does NOT depend on FORGE, logistics,
  the scheduler, Telegram, or the DB. Aligns with the project decision that logistics and
  Telegram scheduling stay optional and the app works as a pure forge-output tool.
- **Zero changes to existing logic.** `metadata_pool.py`, `database.py`, `videos.py`,
  `telegram_core.py`, `updater.py`, the FORGE flow, the scheduler, and the DB behave
  byte-identically. The only edit to `gui_premium_v7.py` is adding one new screen + one nav
  entry.
- **No web stack.** Rendering is pure Pillow. No headless browser, no HTML→PNG runtime.
- **No extraction of OOPSIE's IP.** Icons/fonts/templates are self-authored or sourced from
  free assets; only the *idea* and the *real platforms' public UI* are referenced.

## Chosen direction (from brainstorming)

- **Scope:** build all three platforms (Reddit / X / IG) in one pass.
- **Output:** static PNG per card is the core deliverable; card-intro video is a designed-in
  stretch goal (clear seam, not built in v1).
- **Fields:** random-generated defaults with optional pinned overrides.
- **Render:** pure Pillow — code-drawn chrome + bundled monochrome icon PNGs that are tinted
  at render time + a bundled font for cross-machine consistency.
- **Integration:** new standalone screen with its own media picker; the engine is a plain
  callable so FORGE can optionally hook it later.
- **Theme:** user chooses dark/light per batch (X forced dark).
- **Batch model:** `len(media) × len(platforms) × copies` cards.
- **Extra overrides (added during review):** counts can be Random or Manual; text language is
  selectable EN / ES / PT.

## 1. Architecture / module layout

New pure-logic module `social_cards.py` — **no tkinter import**, so it is unit-testable and
callable from FORGE later.

```
social_cards.py
  ├─ frame grab:   ffprobe (dims/duration) + ffmpeg (extract 1 mid-clip frame → PNG)
  │                reuses the metadata_pool _NO_WINDOW creationflags pattern
  ├─ fake-data:    rand_username / rand_handle / rand_display_name / rand_count /
  │                fmt_count / rand_age  + bundled EN/ES/PT word, subreddit, caption pools
  ├─ renderers:    render_reddit() / render_x() / render_ig()  → each returns a PIL.Image
  ├─ engine:       generate_cards(media_paths, platforms, copies, theme, overrides, out_dir)
  │                → list[str]  (written PNG paths)
  └─ (stretch)     card_to_video(card_png, source_video) → mp4 with card intro
assets/social_icons/   ← bundled monochrome PNGs, tinted at render:
                          upvote, downvote, comment, share, save, heart, retweet, reply,
                          views, verified, more
assets/fonts/          ← bundled font (e.g. DejaVuSans / Segoe UI fallback) for consistent text
```

GUI side: a new `_build_cards_frame()` in `gui_premium_v7.py` only. Rendering/data logic
never touches tkinter.

## 2. The compositing engine

```python
generate_cards(
    media_paths: list[str],   # videos and/or images the user added
    platforms:   list[str],   # subset of ["reddit", "x", "ig"]
    copies:      int,         # cards per media per platform
    theme:       str,         # "dark" | "light"   (X always dark)
    overrides:   dict,        # pinned fields — see below
    out_dir:     str,
) -> list[str]                # written PNG paths
```

`overrides` shape:

```python
{
    "lang":     "en" | "es" | "pt",         # required; picks text pool + UI strings
    "counts":   "random" | "manual",        # required
    "title":    str | None,                 # pinned post title / tweet / caption text
    "username": str | None,                 # pinned username
    # when counts == "manual", the relevant keys are read verbatim (else ignored):
    "reddit_votes": int | None, "reddit_comments": int | None,
    "x_likes": int | None, "x_retweets": int | None,
    "x_replies": int | None, "x_views": int | None,
    "ig_likes": int | None,
}
```

Flow, per `(media × platform × copy)`:

1. **Thumbnail.** Video → ffmpeg grabs one mid-clip frame to a temp PNG (dims from ffprobe).
   Image → loaded directly.
2. **Roll fields.** Fresh random values for username/counts/timestamp/text. Any field present
   in `overrides` (pinned text, pinned username, or manual counts) replaces the random roll.
3. **Render.** Call the platform renderer → `PIL.Image`.
4. **Save.** Write PNG to `out_dir` with a templated name.

- Total cards = `len(media) × len(platforms) × copies`.
- Runs on a worker thread (same pattern as FORGE) so the GUI never freezes; progress is
  reported back to a status label via the tk main thread.
- **Media aspect:** each card has a fixed media slot. The source frame is **center-cropped to
  fill** the slot (no letterbox bars — reads as native).

## 3. Renderers + fake-data

Each renderer draws on a fixed-width canvas (~1080px, height varies), pastes tinted icon
PNGs, draws text with the bundled font, and pastes the media into the slot. Sized to look
like a screenshot, not a full app screen.

### Reddit — `render_reddit` (dark or light)
- Header row: `r/subreddit · u/username · {age}`.
- Post title (1–2 lines).
- Media slot (~4:5 or 1:1).
- Left rail: upvote ▲ + vote count + downvote ▼.
- Footer icon row: comment count, share, save.
- Random fields: subreddit (bundled pool per language), username, vote count (weighted range,
  formatted `12.4k`), comment count, age (`3h`, `1d`).

### Twitter/X — `render_x` (always dark)
- Row: avatar circle (colored, initial glyph — no real photos) + display name + optional ✔
  verified badge (random on/off) + `@handle` + `· {age}`.
- Tweet text (bundled caption pool per language).
- Media slot.
- Action row: reply / retweet / like / view counts.
- Random fields: display name, handle, tweet text, and counts kept **internally consistent**
  (views ≥ likes ≥ retweets ≥ replies).

### Instagram/Threads — `render_ig` (dark or light)
- Header: avatar (initial glyph) + username + `⋯`.
- Media slot (square or 4:5).
- Action row: ♥ 💬 ➤ … 🔖 (tinted icons).
- Like-count line, localized (`liked by X and N others` / `A X y N personas más les gusta` /
  `Curtido por X e outras N pessoas`).
- Caption line: `username` + text.
- Random fields: username, like count, caption.

### Shared fake-data helpers (module-level)
- `rand_username()`, `rand_handle()`, `rand_display_name()`
- `rand_count(lo, hi) -> int`; `fmt_count(n) -> str` → `1.2k` / `48.3k` / `1.1M`
- `rand_age() -> str` → `3h` / `1d` (localized formatting)
- Bundled per-language pools: word/name parts, subreddits, captions/tweets, UI strings.

Pinnable via `overrides`: post title / tweet / caption text, username, and (in manual mode)
the counts. Everything else stays random per copy.

## 4. GUI screen — `_build_cards_frame`

New sidebar entry under **Contenido**: `🪪 Tarjetas` → nav key `"Cards"`. Scrollable frame
(the Forge `cb1d77d` scroll-wrapper pattern). Built entirely from the existing component kit
(`PageHeader`, `Card`, `PrimaryButton`, `GhostButton`, `Stepper`, `SegmentedControl`,
`ToggleRow`). Top-to-bottom:

- `PageHeader("CONTENIDO", "Tarjetas Sociales", "Genera capturas falsas de Reddit, X e Instagram con tu media dentro.")`
- **Card "Media":** file list + `PrimaryButton` ＋ Agregar / `GhostButton` Quitar (mirrors the
  Forge video list).
- **Card "Plataformas":** three `ToggleRow` switches — Reddit / X / Instagram.
- **Card "Opciones":**
  - `Stepper` "Copias por media".
  - `SegmentedControl` tema: `Oscuro / Claro` (X ignores, stays dark).
  - `SegmentedControl` idioma: `EN / ES / PT`.
  - `SegmentedControl` cantidades: `Aleatorio / Manual` — Manual reveals count inputs for each
    enabled platform.
  - Optional pinned-override text inputs: título/tweet/caption, username — blank = random.
- **Card "Salida":** output-folder picker (`GhostButton` Examinar + path label).
- **Bottom bar:** `PrimaryButton` "Generar Tarjetas" (spawns the worker thread; progress in a
  status label) + `GhostButton` "Abrir carpeta".

Nav wiring: add `("🪪   Tarjetas", "Cards")` to the **Contenido** group in `_build_sidebar`,
add `"Cards"` to the frame list + a `_build_cards_frame()` call in `_build_content_area`. No
other screen changes.

## 5. Dependencies, assets, output, testing

**Dependencies:** add `Pillow` to `requirements.txt` (CustomTkinter already pulls it in
transitively; make it explicit). ffmpeg + ffprobe already required and on PATH. No new heavy
runtime deps.

**Bundled assets:**
- `assets/social_icons/` — monochrome PNGs tinted at render: upvote, downvote, comment,
  share, save, heart, retweet, reply, views, verified, more. Self-authored simple geometric
  glyphs.
- `assets/fonts/` — one bundled font so text renders identically across machines.

**Output naming:** `{platform}_{mediastem}_{copy}.png` (e.g. `reddit_clip01_1.png`). Stretch
video-intro reuses the stem with `.mp4`.

**Testing** — `tests/test_social_cards.py`, pure-logic, no GUI:
- `fmt_count()`: `1200→"1.2k"`, `48300→"48.3k"`, `1_100_000→"1.1M"`.
- `rand_count(lo, hi)` stays in range; X counts internally consistent
  (views ≥ likes ≥ retweets ≥ replies).
- Each renderer returns a `PIL.Image` of the expected size for a dummy 100×100 media input,
  across all three languages and dark+light.
- `overrides` pinning: pinned title/username appears; manual counts appear verbatim.
- `generate_cards` writes exactly `len(media) × len(platforms) × copies` files.

**Existing test suite** must still pass (proves no logic changed).

## 6. Explicitly untouched

`metadata_pool.py`, `database.py`, `videos.py`, `telegram_core.py`, `updater.py`,
`Organizador.py`, the FORGE flow, the scheduler, anti-collision distribution, all existing
command handlers and instance variables, threading model, and DB schema/access.

## 7. Risks

- **Fidelity ceiling.** Pillow-drawn chrome won't be pixel-perfect vs a real screenshot; good
  enough for the ad/spoof use case, and improvable by refining icons/spacing. Accepted.
- **Platform UI drift.** Reddit/X/IG periodically restyle their UI; templates may look dated
  and need occasional touch-ups. Accepted (data-driven layout constants ease this).
- **ffmpeg frame grab** on odd/variable-fps or broken videos may need a fallback (grab first
  frame if mid-clip seek fails).
- **Font/emoji rendering** for action-row glyphs — prefer bundled icon PNGs over unicode/emoji
  to avoid font-dependent inconsistency (already the chosen approach).

## Appendix — stretch goal (not in v1)

**Card-intro video** (`card_to_video`): render the card PNG as the first N seconds of an
output video (optionally a subtle zoom), then cut to the real source clip — via ffmpeg
concat/overlay. Designed-in seam: `generate_cards` already produces the card PNG + knows the
source path, so a later pass wraps them without reworking the engine.
