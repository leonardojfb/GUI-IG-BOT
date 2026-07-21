# Social Cards Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone screen + engine that generates fake Reddit / Twitter-X / Instagram post screenshots with the user's own video frame or image composited inside, filled with randomized-or-pinned fields.

**Architecture:** A pure-logic module `social_cards.py` (no tkinter) does all rendering with Pillow: `build_fields()` rolls the fake data, three `render_*()` functions draw platform chrome + paste the media, and `generate_cards()` orchestrates a batch. A single new CustomTkinter screen (`_build_cards_frame` in `gui_premium_v7.py`) collects inputs and calls the engine on a worker thread. Chrome icons are drawn procedurally with `PIL.ImageDraw`; text uses a system-font resolver. Nothing else in the app changes.

**Tech Stack:** Python 3, Pillow (`PIL`), CustomTkinter, ffmpeg/ffprobe (already on PATH), pytest.

## Global Constraints

- **Zero logic changes** to `metadata_pool.py`, `database.py`, `videos.py`, `telegram_core.py`, `updater.py`, `Organizador.py`, the FORGE flow, the scheduler, or the DB. The ONLY edit to an existing file is adding the new screen + nav entry to `gui_premium_v7.py`, and adding `Pillow` to `requirements.txt`.
- **No web stack.** Rendering is pure Pillow. No headless browser, no HTML→PNG.
- **No OOPSIE IP.** Icons are self-authored procedural drawings; templates reference only the real platforms' public UI.
- **`social_cards.py` never imports tkinter** — it must stay unit-testable and FORGE-callable later.
- **Canvas width is 1080px** for all three platforms.
- **Windows subprocess:** every ffmpeg/ffprobe call passes `creationflags=metadata_pool._NO_WINDOW` (the app runs under `pythonw`; a bare console window freezes the machine).
- **X (Twitter) is always dark** regardless of the theme argument.
- **Languages:** `"en"`, `"es"`, `"pt"`. Unknown language falls back to `"en"`.
- **Repo:** the real git repo is `Método IG VIDEOS v2.0/`. Run all git from there. The parent folder has a broken `.git` — never git from it.
- **`git add` only the files a task names — never `git add -A`.**
- **GUI is non-interactive; do NOT launch it.** Verify with `python -m py_compile` + `pytest`.

---

### Task 1: Module scaffold — count/format/random helpers

**Files:**
- Create: `social_cards.py`
- Create: `tests/test_social_cards.py`
- Modify: `requirements.txt` (add `Pillow`)

**Interfaces:**
- Produces:
  - `fmt_count(n: int) -> str` → `"1.2k"`, `"48.3k"`, `"1.1M"`, `"999"`
  - `rand_count(lo: int, hi: int) -> int` (clamped `lo>=1`, `hi>=lo`)
  - `rand_x_counts() -> dict` with keys `views, likes, retweets, replies` where `views >= likes >= retweets >= replies`
  - `rand_age() -> str`, `rand_username(lang="en") -> str`, `rand_handle(name: str) -> str`, `rand_display_name(lang="en") -> str`
  - `POOLS: dict`, `UI_STRINGS: dict`

- [ ] **Step 1: Write the failing test**

Create `tests/test_social_cards.py`:

```python
import os
import social_cards as sc


def test_fmt_count():
    assert sc.fmt_count(999) == "999"
    assert sc.fmt_count(1000) == "1k"
    assert sc.fmt_count(1200) == "1.2k"
    assert sc.fmt_count(48300) == "48.3k"
    assert sc.fmt_count(1_100_000) == "1.1M"


def test_rand_count_in_range():
    for _ in range(200):
        v = sc.rand_count(10, 50)
        assert 10 <= v <= 50
    # degenerate / inverted inputs are clamped, never raise
    assert sc.rand_count(0, 0) >= 1
    assert sc.rand_count(100, 5) >= 1


def test_rand_x_counts_consistent():
    for _ in range(200):
        c = sc.rand_x_counts()
        assert c["views"] >= c["likes"] >= c["retweets"] >= c["replies"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'social_cards'`.

- [ ] **Step 3: Write minimal implementation**

Create `social_cards.py`:

```python
"""Social Cards — fake Reddit/X/Instagram post-screenshot generator.

Pure logic (NO tkinter import) so it stays unit-testable and FORGE-callable.
Rendering is pure Pillow; chrome icons are drawn procedurally.
"""
import os
import random
import re
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

# Reuse the windowless-subprocess flag so ffmpeg/ffprobe never pop a console
# under pythonw. Imported lazily where used to keep this module import-light.

W = 1080  # canvas width for every platform

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


# ── Text pools per language ────────────────────────────────────────────────
POOLS = {
    "en": {
        "adjs": ["silent", "cosmic", "lunar", "urban", "vivid", "quiet", "wild", "amber"],
        "nouns": ["fox", "raven", "pixel", "drift", "echo", "nomad", "spark", "wave"],
        "names": ["Alex Rivera", "Jordan Lee", "Sam Carter", "Taylor Quinn", "Morgan Hale"],
        "subreddits": ["nextfuckinglevel", "oddlysatisfying", "Damnthatsinteresting",
                       "BeAmazed", "interestingasfuck", "MadeMeSmile"],
        "titles": ["This is next level", "I can't stop watching this",
                   "How is this even possible", "Wait for it...", "Absolutely insane skill"],
        "tweets": ["okay this is actually incredible", "no way this is real",
                   "the internet was a mistake (this is not)", "i've watched this 40 times"],
        "captions": ["caught this today \U0001F440", "had to share this one",
                     "wait for the end", "still thinking about this"],
    },
    "es": {
        "adjs": ["silencioso", "cosmico", "lunar", "urbano", "vivido", "salvaje", "ambar"],
        "nouns": ["zorro", "cuervo", "pixel", "eco", "nomada", "chispa", "ola"],
        "names": ["Alex Rivera", "Jordi Leon", "Sam Castro", "Tania Quin", "Mateo Vega"],
        "subreddits": ["videos", "impresionante", "MeParecioIncreible",
                       "curiosidades", "quenoteloscreas"],
        "titles": ["Esto es otro nivel", "No puedo dejar de verlo",
                   "Como es esto posible", "Esperen el final...", "Habilidad brutal"],
        "tweets": ["esto es realmente increible", "no puede ser real",
                   "lo vi 40 veces seguidas", "necesitaba compartir esto"],
        "captions": ["mira lo que grabe hoy \U0001F440", "tenia que compartir esto",
                     "espera el final", "sigo pensando en esto"],
    },
    "pt": {
        "adjs": ["silencioso", "cosmico", "lunar", "urbano", "vivido", "selvagem", "ambar"],
        "nouns": ["raposa", "corvo", "pixel", "eco", "nomade", "faisca", "onda"],
        "names": ["Alex Ribeiro", "Jordi Lima", "Sam Costa", "Tania Quintao", "Mateo Vaz"],
        "subreddits": ["videos", "incrivel", "AchoInteressante", "curiosidades", "Brasil"],
        "titles": ["Isso e outro nivel", "Nao consigo parar de ver",
                   "Como isso e possivel", "Espera o final...", "Habilidade absurda"],
        "tweets": ["isso e realmente incrivel", "nao pode ser real",
                   "assisti 40 vezes seguidas", "precisava compartilhar isso"],
        "captions": ["olha o que gravei hoje \U0001F440", "tinha que compartilhar",
                     "espera o final", "ainda pensando nisso"],
    },
}

UI_STRINGS = {
    "en": {"likes": "{n} likes"},
    "es": {"likes": "{n} Me gusta"},
    "pt": {"likes": "{n} curtidas"},
}


def _lang(lang):
    return lang if lang in POOLS else "en"


# ── Count formatting / randomisation ───────────────────────────────────────
def fmt_count(n):
    n = int(n)
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "k"
    return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"


def rand_count(lo, hi):
    lo = max(1, int(lo))
    hi = max(lo, int(hi))
    return random.randint(lo, hi)


def rand_x_counts():
    views = rand_count(5_000, 2_000_000)
    likes = rand_count(int(views * 0.01), int(views * 0.08))
    retweets = rand_count(int(likes * 0.05), int(likes * 0.25))
    replies = rand_count(int(retweets * 0.10), retweets)
    return {"views": views, "likes": likes, "retweets": retweets, "replies": replies}


def rand_age():
    return random.choice(["1h", "3h", "5h", "8h", "12h", "1d", "2d", "3d"])


def rand_username(lang="en"):
    p = POOLS[_lang(lang)]
    return f"{random.choice(p['adjs'])}{random.choice(p['nouns'])}{random.randint(1, 999)}"


def rand_handle(name):
    return re.sub(r"\W", "", name).lower()[:15] or "user"


def rand_display_name(lang="en"):
    return random.choice(POOLS[_lang(lang)]["names"])
```

Append `Pillow` to `requirements.txt`:

```
customtkinter==5.2.2
requests==2.32.3
tzdata
Pillow>=10.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add social_cards.py tests/test_social_cards.py requirements.txt
git commit -m "feat(cards): social_cards module scaffold + count/random helpers"
```

---

### Task 2: `build_fields` — resolve random + pinned overrides

**Files:**
- Modify: `social_cards.py`
- Test: `tests/test_social_cards.py`

**Interfaces:**
- Consumes: `POOLS`, `UI_STRINGS`, `rand_*`, `fmt_count`, `rand_x_counts` (Task 1).
- Produces: `build_fields(platform: str, lang: str, counts_mode: str, overrides: dict) -> dict`.
  - `platform` in `{"reddit","x","ig"}`; `counts_mode` in `{"random","manual"}`.
  - `overrides` keys (all optional): `title`, `username`, and in manual mode `reddit_votes`, `reddit_comments`, `x_likes`, `x_retweets`, `x_replies`, `x_views`, `ig_likes`.
  - Returned dict keys per platform:
    - reddit: `subreddit, username, age, title, votes, votes_str, comments, comments_str`
    - x: `display_name, handle, verified, age, text, likes, likes_str, retweets, retweets_str, replies, replies_str, views, views_str`
    - ig: `username, avatar_initial, likes, likes_str, likes_line, caption`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_social_cards.py`:

```python
def test_build_fields_reddit_pins():
    f = sc.build_fields("reddit", "en", "random", {"title": "HELLO", "username": "bob"})
    assert f["title"] == "HELLO"
    assert f["username"] == "bob"
    assert f["votes_str"] == sc.fmt_count(f["votes"])


def test_build_fields_manual_counts():
    f = sc.build_fields("reddit", "en", "manual",
                        {"reddit_votes": 123, "reddit_comments": 45})
    assert f["votes"] == 123 and f["comments"] == 45


def test_build_fields_x_manual_and_consistent_random():
    f = sc.build_fields("x", "en", "manual",
                        {"x_views": 900, "x_likes": 80, "x_retweets": 10, "x_replies": 3})
    assert (f["views"], f["likes"], f["retweets"], f["replies"]) == (900, 80, 10, 3)
    assert isinstance(f["verified"], bool)


def test_build_fields_ig_localized_like_line():
    f = sc.build_fields("ig", "es", "manual", {"ig_likes": 1500})
    assert "Me gusta" in f["likes_line"]
    assert f["avatar_initial"] == f["username"][0].upper()


def test_build_fields_unknown_lang_falls_back():
    f = sc.build_fields("reddit", "zz", "random", {})
    assert f["subreddit"] in sc.POOLS["en"]["subreddits"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: FAIL with `AttributeError: module 'social_cards' has no attribute 'build_fields'`.

- [ ] **Step 3: Write minimal implementation**

Add to `social_cards.py`:

```python
def build_fields(platform, lang, counts_mode, overrides):
    lang = _lang(lang)
    o = overrides or {}
    manual = counts_mode == "manual"

    if platform == "reddit":
        votes = int(o["reddit_votes"]) if manual and o.get("reddit_votes") is not None \
            else rand_count(200, 95_000)
        comments = int(o["reddit_comments"]) if manual and o.get("reddit_comments") is not None \
            else rand_count(10, 4_000)
        return {
            "subreddit": random.choice(POOLS[lang]["subreddits"]),
            "username": o.get("username") or rand_username(lang),
            "age": rand_age(),
            "title": o.get("title") or random.choice(POOLS[lang]["titles"]),
            "votes": votes, "votes_str": fmt_count(votes),
            "comments": comments, "comments_str": fmt_count(comments),
        }

    if platform == "x":
        if manual:
            views = int(o.get("x_views") or 0)
            likes = int(o.get("x_likes") or 0)
            retweets = int(o.get("x_retweets") or 0)
            replies = int(o.get("x_replies") or 0)
        else:
            c = rand_x_counts()
            views, likes, retweets, replies = c["views"], c["likes"], c["retweets"], c["replies"]
        name = o.get("username") or rand_display_name(lang)
        return {
            "display_name": name, "handle": rand_handle(name),
            "verified": random.random() < 0.5, "age": rand_age(),
            "text": o.get("title") or random.choice(POOLS[lang]["tweets"]),
            "likes": likes, "likes_str": fmt_count(likes),
            "retweets": retweets, "retweets_str": fmt_count(retweets),
            "replies": replies, "replies_str": fmt_count(replies),
            "views": views, "views_str": fmt_count(views),
        }

    if platform == "ig":
        likes = int(o["ig_likes"]) if manual and o.get("ig_likes") is not None \
            else rand_count(500, 250_000)
        user = o.get("username") or rand_username(lang)
        return {
            "username": user, "avatar_initial": user[0].upper(),
            "likes": likes, "likes_str": fmt_count(likes),
            "likes_line": UI_STRINGS[lang]["likes"].format(n=fmt_count(likes)),
            "caption": o.get("title") or random.choice(POOLS[lang]["captions"]),
        }

    raise ValueError(f"unknown platform: {platform}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: PASS (all Task 1 + Task 2 tests).

- [ ] **Step 5: Commit**

```bash
git add social_cards.py tests/test_social_cards.py
git commit -m "feat(cards): build_fields resolves random + pinned overrides"
```

---

### Task 3: Font resolver + procedural chrome icons

**Files:**
- Modify: `social_cards.py`
- Test: `tests/test_social_cards.py`

**Interfaces:**
- Produces:
  - `_load_font(size: int, bold=False) -> ImageFont` (system-path resolver, falls back to `load_default()`).
  - Icon drawers, each `(draw: ImageDraw, x, y, s, color) -> None`: `draw_upvote`, `draw_downvote`, `draw_comment`, `draw_share`, `draw_heart`, `draw_retweet`, `draw_reply`, `draw_verified`.
  - `draw_avatar(img: Image, x, y, s, initial: str, bg_color) -> None`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_social_cards.py`:

```python
from PIL import Image, ImageDraw


def test_load_font_returns_font():
    assert sc._load_font(20) is not None
    assert sc._load_font(28, bold=True) is not None


def test_icons_draw_without_error():
    img = Image.new("RGB", (80, 80), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for fn in (sc.draw_upvote, sc.draw_downvote, sc.draw_comment, sc.draw_share,
               sc.draw_heart, sc.draw_retweet, sc.draw_reply, sc.draw_verified):
        fn(d, 5, 5, 30, (255, 0, 0))
    sc.draw_avatar(img, 5, 5, 40, "A", (80, 90, 200))
    # something was drawn (not an all-black image)
    assert img.getbbox() is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: FAIL with `AttributeError: module 'social_cards' has no attribute '_load_font'`.

- [ ] **Step 3: Write minimal implementation**

Add to `social_cards.py`:

```python
_FONT_REGULAR = [
    "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf",
]
_FONT_BOLD = [
    "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _load_font(size, bold=False):
    for path in (_FONT_BOLD if bold else _FONT_REGULAR):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size)  # Pillow >= 10.1 accepts a size
    except TypeError:
        return ImageFont.load_default()


def draw_upvote(d, x, y, s, color):
    d.polygon([(x + s / 2, y), (x + s, y + s * 0.55), (x + s * 0.7, y + s * 0.55),
               (x + s * 0.7, y + s), (x + s * 0.3, y + s), (x + s * 0.3, y + s * 0.55),
               (x, y + s * 0.55)], fill=color)


def draw_downvote(d, x, y, s, color):
    d.polygon([(x + s / 2, y + s), (x + s, y + s * 0.45), (x + s * 0.7, y + s * 0.45),
               (x + s * 0.7, y), (x + s * 0.3, y), (x + s * 0.3, y + s * 0.45),
               (x, y + s * 0.45)], fill=color)


def draw_comment(d, x, y, s, color):
    d.rounded_rectangle([x, y, x + s, y + s * 0.78], radius=6, outline=color, width=3)
    d.polygon([(x + s * 0.2, y + s * 0.78), (x + s * 0.42, y + s * 0.78),
               (x + s * 0.2, y + s)], fill=color)


def draw_share(d, x, y, s, color):
    d.line([(x + s / 2, y + s), (x + s / 2, y)], fill=color, width=3)
    d.polygon([(x + s / 2, y), (x + s * 0.25, y + s * 0.3),
               (x + s * 0.75, y + s * 0.3)], fill=color)


def draw_heart(d, x, y, s, color):
    d.ellipse([x, y, x + s / 2, y + s / 2], fill=color)
    d.ellipse([x + s / 2, y, x + s, y + s / 2], fill=color)
    d.polygon([(x, y + s / 4), (x + s, y + s / 4), (x + s / 2, y + s)], fill=color)


def draw_retweet(d, x, y, s, color):
    d.line([(x, y + s * 0.7), (x, y + s * 0.3), (x + s * 0.6, y + s * 0.3)],
           fill=color, width=3)
    d.polygon([(x + s * 0.55, y + s * 0.12), (x + s * 0.55, y + s * 0.48),
               (x + s * 0.85, y + s * 0.3)], fill=color)
    d.line([(x + s, y + s * 0.3), (x + s, y + s * 0.7), (x + s * 0.4, y + s * 0.7)],
           fill=color, width=3)
    d.polygon([(x + s * 0.45, y + s * 0.52), (x + s * 0.45, y + s * 0.88),
               (x + s * 0.15, y + s * 0.7)], fill=color)


def draw_reply(d, x, y, s, color):
    d.rounded_rectangle([x, y, x + s, y + s * 0.75], radius=6, outline=color, width=3)
    d.polygon([(x + s * 0.25, y + s * 0.75), (x + s * 0.5, y + s * 0.75),
               (x + s * 0.25, y + s)], fill=color)


def draw_verified(d, x, y, s, color):
    d.ellipse([x, y, x + s, y + s], fill=color)
    d.line([(x + s * 0.28, y + s * 0.5), (x + s * 0.45, y + s * 0.68),
            (x + s * 0.72, y + s * 0.32)], fill=(255, 255, 255), width=3)


def draw_avatar(img, x, y, s, initial, bg_color):
    d = ImageDraw.Draw(img)
    d.ellipse([x, y, x + s, y + s], fill=bg_color)
    f = _load_font(int(s * 0.5), bold=True)
    tw = d.textlength(initial, font=f)
    d.text((x + s / 2 - tw / 2, y + s * 0.22), initial, font=f, fill=(255, 255, 255))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add social_cards.py tests/test_social_cards.py
git commit -m "feat(cards): font resolver + procedural chrome icons"
```

---

### Task 4: Media prep — crop-to-fill + thumbnail loader

**Files:**
- Modify: `social_cards.py`
- Test: `tests/test_social_cards.py`

**Interfaces:**
- Produces:
  - `_crop_to_fill(img: Image, tw: int, th: int) -> Image` (center-crop to fill, no bars).
  - `load_media_thumbnail(path: str) -> Image` (image → open; video ext → ffmpeg mid-clip frame with first-frame fallback).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_social_cards.py`:

```python
def test_crop_to_fill_dims():
    out = sc._crop_to_fill(Image.new("RGB", (200, 100), (0, 120, 200)), 300, 300)
    assert out.size == (300, 300)
    out2 = sc._crop_to_fill(Image.new("RGB", (100, 400), (0, 120, 200)), 300, 300)
    assert out2.size == (300, 300)


def test_load_media_thumbnail_image(tmp_path):
    p = tmp_path / "pic.png"
    Image.new("RGB", (640, 480), (12, 130, 200)).save(p)
    img = sc.load_media_thumbnail(str(p))
    assert img.size == (640, 480)
    assert img.mode == "RGB"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: FAIL with `AttributeError: ... '_crop_to_fill'`.

- [ ] **Step 3: Write minimal implementation**

Add to `social_cards.py`:

```python
def _crop_to_fill(img, tw, th):
    img = img.convert("RGB")
    sw, sh = img.size
    scale = max(tw / sw, th / sh)
    nw, nh = max(tw, int(sw * scale)), max(th, int(sh * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def load_media_thumbnail(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_EXTS:
        return _grab_video_frame(path)
    return Image.open(path).convert("RGB")


def _grab_video_frame(path):
    import metadata_pool  # reuse ffprobe + _NO_WINDOW; read-only, no logic change
    no_window = metadata_pool._NO_WINDOW
    try:
        _, _, dur, _ = metadata_pool._probe_video_info(path)
    except Exception:
        dur = 0.0
    ts = max(0.0, dur / 2)
    tmp = tempfile.mktemp(suffix=".png")
    subprocess.run(["ffmpeg", "-y", "-ss", str(ts), "-i", path, "-frames:v", "1", tmp],
                   capture_output=True, creationflags=no_window)
    if not os.path.exists(tmp):  # seek failed → grab the first frame
        subprocess.run(["ffmpeg", "-y", "-i", path, "-frames:v", "1", tmp],
                       capture_output=True, creationflags=no_window)
    img = Image.open(tmp).convert("RGB")
    img.load()
    try:
        os.remove(tmp)
    except OSError:
        pass
    return img
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add social_cards.py tests/test_social_cards.py
git commit -m "feat(cards): media crop-to-fill + ffmpeg thumbnail loader"
```

---

### Task 5: `render_reddit`

**Files:**
- Modify: `social_cards.py`
- Test: `tests/test_social_cards.py`

**Interfaces:**
- Consumes: `build_fields` output for `"reddit"`, `_crop_to_fill`, `_load_font`, `draw_upvote/downvote/comment/share`.
- Produces: `render_reddit(media: Image, fields: dict, theme="dark") -> Image` (width 1080).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_social_cards.py`:

```python
def _dummy_media():
    return Image.new("RGB", (500, 500), (10, 120, 200))


def test_render_reddit_dims_dark_and_light():
    f = sc.build_fields("reddit", "en", "random", {})
    for theme in ("dark", "light"):
        img = sc.render_reddit(_dummy_media(), f, theme)
        assert img.width == 1080
        assert img.height > 900
        assert img.mode == "RGB"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: FAIL with `AttributeError: ... 'render_reddit'`.

- [ ] **Step 3: Write minimal implementation**

Add to `social_cards.py`:

```python
_THEMES = {
    "reddit": {
        "dark": {"bg": (26, 26, 27), "text": (215, 218, 220), "muted": (129, 131, 132),
                 "line": (52, 53, 54), "up": (255, 69, 0)},
        "light": {"bg": (255, 255, 255), "text": (28, 28, 28), "muted": (120, 124, 130),
                  "line": (237, 239, 241), "up": (255, 69, 0)},
    },
    "x": {"dark": {"bg": (0, 0, 0), "text": (231, 233, 234), "muted": (113, 118, 123),
                   "line": (47, 51, 54), "like": (249, 24, 128), "rt": (0, 186, 124),
                   "reply": (29, 155, 240), "verified": (29, 155, 240),
                   "avatar": (83, 100, 113)}},
    "ig": {
        "dark": {"bg": (0, 0, 0), "text": (250, 250, 250), "muted": (168, 168, 168),
                 "line": (38, 38, 38), "heart": (255, 48, 64), "avatar": (60, 70, 160)},
        "light": {"bg": (255, 255, 255), "text": (38, 38, 38), "muted": (142, 142, 142),
                  "line": (219, 219, 219), "heart": (255, 48, 64), "avatar": (60, 70, 160)},
    },
}


def render_reddit(media, fields, theme="dark"):
    c = _THEMES["reddit"]["light" if theme == "light" else "dark"]
    pad = 32
    slot = 1080
    header_h, title_h, footer_h = 92, 96, 76
    H = header_h + title_h + slot + footer_h
    img = Image.new("RGB", (W, H), c["bg"])
    d = ImageDraw.Draw(img)

    f_sub = _load_font(32, bold=True)
    f_meta = _load_font(28)
    f_title = _load_font(40, bold=True)
    f_stat = _load_font(30, bold=True)

    # header: r/sub · u/user · age
    sub = f"r/{fields['subreddit']}"
    d.text((pad, 30), sub, font=f_sub, fill=c["text"])
    sw = d.textlength(sub, font=f_sub)
    d.text((pad + sw + 16, 34), f"· u/{fields['username']} · {fields['age']}",
           font=f_meta, fill=c["muted"])

    # title
    d.text((pad, header_h + 8), fields["title"], font=f_title, fill=c["text"])

    # media
    my = header_h + title_h
    img.paste(_crop_to_fill(media, slot, slot), (0, my))

    # footer: upvote count downvote  |  comment count  |  share
    fy = my + slot + 20
    x = pad
    draw_upvote(d, x, fy, 30, c["up"])
    d.text((x + 42, fy + 2), fields["votes_str"], font=f_stat, fill=c["text"])
    x += 42 + d.textlength(fields["votes_str"], font=f_stat) + 18
    draw_downvote(d, x, fy, 30, c["muted"])
    x += 70
    draw_comment(d, x, fy, 30, c["muted"])
    d.text((x + 42, fy + 2), fields["comments_str"], font=f_stat, fill=c["muted"])
    x += 42 + d.textlength(fields["comments_str"], font=f_stat) + 40
    draw_share(d, x, fy, 30, c["muted"])
    return img
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add social_cards.py tests/test_social_cards.py
git commit -m "feat(cards): render_reddit template"
```

---

### Task 6: `render_x`

**Files:**
- Modify: `social_cards.py`
- Test: `tests/test_social_cards.py`

**Interfaces:**
- Consumes: `build_fields` output for `"x"`, `_crop_to_fill`, `_load_font`, `draw_avatar/verified/reply/retweet/heart`.
- Produces: `render_x(media: Image, fields: dict, theme="dark") -> Image` (always dark; `theme` accepted for a uniform call signature but ignored).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_social_cards.py`:

```python
def test_render_x_dims():
    f = sc.build_fields("x", "en", "random", {})
    img = sc.render_x(_dummy_media(), f)
    assert img.width == 1080
    assert img.height > 700
    # dark background regardless of theme arg
    img_light = sc.render_x(_dummy_media(), f, theme="light")
    assert img_light.getpixel((5, 5)) == (0, 0, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: FAIL with `AttributeError: ... 'render_x'`.

- [ ] **Step 3: Write minimal implementation**

Add to `social_cards.py`:

```python
def render_x(media, fields, theme="dark"):
    c = _THEMES["x"]["dark"]  # X is always dark
    pad = 32
    slot_w, slot_h = 1016, 640
    top_h = 120
    text_h = 84
    action_h = 80
    H = top_h + text_h + slot_h + 40 + action_h
    img = Image.new("RGB", (W, H), c["bg"])
    d = ImageDraw.Draw(img)

    f_name = _load_font(32, bold=True)
    f_meta = _load_font(28)
    f_text = _load_font(34)
    f_stat = _load_font(26)

    # avatar + name + verified + handle · age
    av = 84
    draw_avatar(img, pad, 24, av, fields["display_name"][0].upper(), c["avatar"])
    nx = pad + av + 18
    d.text((nx, 30), fields["display_name"], font=f_name, fill=c["text"])
    nw = d.textlength(fields["display_name"], font=f_name)
    bx = nx + nw + 10
    if fields["verified"]:
        draw_verified(d, bx, 34, 28, c["verified"])
        bx += 36
    d.text((nx, 70), f"@{fields['handle']} · {fields['age']}",
           font=f_meta, fill=c["muted"])

    # tweet text
    d.text((pad, top_h), fields["text"], font=f_text, fill=c["text"])

    # media (rounded look via plain paste; rounded corners optional)
    my = top_h + text_h
    img.paste(_crop_to_fill(media, slot_w, slot_h), (pad, my))

    # action row: reply retweet like  + views
    ay = my + slot_h + 30
    x = pad
    draw_reply(d, x, ay, 30, c["muted"])
    d.text((x + 42, ay + 2), fields["replies_str"], font=f_stat, fill=c["muted"])
    x += 200
    draw_retweet(d, x, ay, 30, c["rt"])
    d.text((x + 42, ay + 2), fields["retweets_str"], font=f_stat, fill=c["muted"])
    x += 200
    draw_heart(d, x, ay + 3, 28, c["like"])
    d.text((x + 42, ay + 2), fields["likes_str"], font=f_stat, fill=c["muted"])
    x += 200
    d.text((x, ay + 2), f"{fields['views_str']} views", font=f_stat, fill=c["muted"])
    return img
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add social_cards.py tests/test_social_cards.py
git commit -m "feat(cards): render_x template"
```

---

### Task 7: `render_ig`

**Files:**
- Modify: `social_cards.py`
- Test: `tests/test_social_cards.py`

**Interfaces:**
- Consumes: `build_fields` output for `"ig"`, `_crop_to_fill`, `_load_font`, `draw_avatar/heart/comment/share`.
- Produces: `render_ig(media: Image, fields: dict, theme="dark") -> Image` (width 1080; dark or light).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_social_cards.py`:

```python
def test_render_ig_dims_dark_and_light():
    f = sc.build_fields("ig", "es", "manual", {"ig_likes": 1500})
    for theme in ("dark", "light"):
        img = sc.render_ig(_dummy_media(), f, theme)
        assert img.width == 1080
        assert img.height > 1100
        assert img.mode == "RGB"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: FAIL with `AttributeError: ... 'render_ig'`.

- [ ] **Step 3: Write minimal implementation**

Add to `social_cards.py`:

```python
def render_ig(media, fields, theme="dark"):
    c = _THEMES["ig"]["light" if theme == "light" else "dark"]
    pad = 28
    slot = 1080
    header_h = 100
    action_h = 72
    likes_h = 48
    caption_h = 56
    H = header_h + slot + action_h + likes_h + caption_h
    img = Image.new("RGB", (W, H), c["bg"])
    d = ImageDraw.Draw(img)

    f_user = _load_font(30, bold=True)
    f_body = _load_font(28)
    f_likes = _load_font(28, bold=True)

    # header: avatar + username + ...
    av = 64
    draw_avatar(img, pad, 18, av, fields["avatar_initial"], c["avatar"])
    d.text((pad + av + 16, 34), fields["username"], font=f_user, fill=c["text"])
    d.text((W - pad - 20, 30), "⋯", font=f_user, fill=c["text"])

    # media
    img.paste(_crop_to_fill(media, slot, slot), (0, header_h))

    # action row: heart comment share ... save
    ay = header_h + slot + 18
    x = pad
    draw_heart(d, x, ay, 32, c["heart"])
    x += 56
    draw_comment(d, x, ay, 32, c["text"])
    x += 56
    draw_share(d, x, ay, 32, c["text"])

    # likes line
    ly = header_h + slot + action_h - 4
    d.text((pad, ly), fields["likes_line"], font=f_likes, fill=c["text"])

    # caption: username + text
    cy = ly + likes_h
    d.text((pad, cy), fields["username"], font=f_likes, fill=c["text"])
    uw = d.textlength(fields["username"], font=f_likes)
    d.text((pad + uw + 12, cy), fields["caption"], font=f_body, fill=c["text"])
    return img
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add social_cards.py tests/test_social_cards.py
git commit -m "feat(cards): render_ig template"
```

---

### Task 8: `generate_cards` — batch engine

**Files:**
- Modify: `social_cards.py`
- Test: `tests/test_social_cards.py`

**Interfaces:**
- Consumes: `load_media_thumbnail`, `build_fields`, `render_reddit/x/ig` (Tasks 4–7).
- Produces:
  `generate_cards(media_paths, platforms, copies, theme, overrides, out_dir, progress=None) -> list[str]`
  - `overrides` carries `lang` and `counts` (mode) plus the pinnable keys.
  - Returns written PNG paths; count == `len(media_paths) * len(platforms) * copies`.
  - `progress(done: int, total: int)` optional callback.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_social_cards.py`:

```python
def test_generate_cards_count_and_names(tmp_path):
    media = tmp_path / "clip01.png"
    Image.new("RGB", (400, 400), (10, 120, 200)).save(media)
    out = tmp_path / "out"
    paths = sc.generate_cards([str(media)], ["reddit", "x", "ig"], 2,
                              "dark", {"lang": "en", "counts": "random"}, str(out))
    assert len(paths) == 6  # 1 media * 3 platforms * 2 copies
    assert all(os.path.exists(p) for p in paths)
    names = [os.path.basename(p) for p in paths]
    assert "reddit_clip01_1.png" in names
    assert "ig_clip01_2.png" in names


def test_generate_cards_progress_callback(tmp_path):
    media = tmp_path / "v.png"
    Image.new("RGB", (300, 300), (0, 0, 0)).save(media)
    seen = []
    sc.generate_cards([str(media)], ["reddit"], 3, "dark",
                      {"lang": "en", "counts": "random"}, str(tmp_path / "o"),
                      progress=lambda done, total: seen.append((done, total)))
    assert seen[-1] == (3, 3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: FAIL with `AttributeError: ... 'generate_cards'`.

- [ ] **Step 3: Write minimal implementation**

Add to `social_cards.py`:

```python
_RENDERERS = {"reddit": render_reddit, "x": render_x, "ig": render_ig}


def generate_cards(media_paths, platforms, copies, theme, overrides, out_dir, progress=None):
    os.makedirs(out_dir, exist_ok=True)
    lang = (overrides or {}).get("lang", "en")
    counts_mode = (overrides or {}).get("counts", "random")
    total = len(media_paths) * len(platforms) * copies
    written = []
    done = 0
    for media_path in media_paths:
        stem = os.path.splitext(os.path.basename(media_path))[0]
        stem = re.sub(r"\s+", "_", stem)
        thumb = load_media_thumbnail(media_path)
        for platform in platforms:
            renderer = _RENDERERS[platform]
            for copy_num in range(1, copies + 1):
                fields = build_fields(platform, lang, counts_mode, overrides)
                card = renderer(thumb, fields, theme)
                out_name = f"{platform}_{stem}_{copy_num}.png"
                out_path = os.path.join(out_dir, out_name)
                card.save(out_path)
                written.append(out_path)
                done += 1
                if progress:
                    progress(done, total)
    return written
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_social_cards.py -q`
Expected: PASS (full file green).

- [ ] **Step 5: Commit**

```bash
git add social_cards.py tests/test_social_cards.py
git commit -m "feat(cards): generate_cards batch engine"
```

---

### Task 9: GUI screen + nav wiring

**Files:**
- Modify: `gui_premium_v7.py`
  - `_build_sidebar` nav group (~line 868)
  - `_build_content_area` frame list + build call (~lines 924, 938)
  - add `_build_cards_frame` + handlers (place near `_build_forge_frame`, ~line 3249)

**Interfaces:**
- Consumes: `social_cards.generate_cards`; component kit (`PageHeader`, `Card`, `PrimaryButton`, `GhostButton`, `Stepper`, `SegmentedControl`, `ToggleRow`); `WorkerThread`; `self.themed`; tokens.
- Produces: a `"Cards"` frame + nav item; handlers `cards_add_media`, `cards_remove_media`, `cards_pick_out`, `cards_open_out`, `_cards_toggle_counts`, `cards_generate`.

**Note:** GUI is non-interactive — do NOT launch it. Verify with `py_compile` + `pytest`.

- [ ] **Step 1: Add the nav entry**

In `_build_sidebar`, extend the **Contenido** group (currently `[("🔮   Forge", "Forge"), ("🎬   Tandas", "Tandas")]`) to include Tarjetas:

```python
            ("Contenido",    [("🔮   Forge", "Forge"), ("🎬   Tandas", "Tandas"),
                              ("🪪   Tarjetas", "Cards")]),
```

- [ ] **Step 2: Register the frame**

In `_build_content_area`, add `"Cards"` to the frame-name list:

```python
        for name in ["Dashboard", "Equipo", "Tandas", "Logistica", "Telegram", "Cuentas", "VerifyLegacy", "AIAdvisor", "Forge", "Actualizaciones", "Cards"]:
```

and add the build call after `self._build_forge_frame()`:

```python
        self._build_forge_frame()
        self._build_cards_frame()
        self._build_updates_frame()
```

- [ ] **Step 3: Add the screen builder + handlers**

Add these methods to the class (next to `_build_forge_frame`). Full code:

```python
    def _build_cards_frame(self):
        import social_cards  # local import keeps startup light
        self._social_cards = social_cards
        self.cards_media_paths = []
        self.cards_out_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "tarjetas_generadas")

        f = self._frames["Cards"]
        f.grid_rowconfigure(0, weight=1)
        f.grid_columnconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(f, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        PageHeader(scroll, kicker="CONTENIDO", title="Tarjetas Sociales",
                   description="Genera capturas falsas de Reddit, X e Instagram con tu media dentro."
                   ).grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))

        # ── Media ──
        media_card = Card(scroll, title="Media")
        media_card.grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 0))
        self.cards_lst = tk.Listbox(
            media_card.body, bg=self.themed(BG_INPUT), fg=self.themed(TEXT_BODY),
            selectbackground=self.themed(ACCENT), selectforeground=self.themed(ACCENT_TEXT),
            selectmode=tk.EXTENDED, borderwidth=0, highlightthickness=1,
            highlightbackground=self.themed(BORDER), font=FONT_BODY, height=6)
        self.cards_lst.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        mb = ctk.CTkFrame(media_card.body, fg_color="transparent")
        mb.grid(row=1, column=0, sticky="ew")
        PrimaryButton(mb, text="＋  Agregar", command=self.cards_add_media).pack(side="left", padx=(0, 8))
        GhostButton(mb, text="−  Quitar", command=self.cards_remove_media).pack(side="left")

        # ── Plataformas ──
        plat_card = Card(scroll, title="Plataformas")
        plat_card.grid(row=2, column=0, sticky="ew", padx=24, pady=(14, 0))
        self.cards_plat_vars = {"reddit": tk.BooleanVar(value=True),
                                "x": tk.BooleanVar(value=True),
                                "ig": tk.BooleanVar(value=True)}
        for i, (k, lbl) in enumerate([("reddit", "Reddit"), ("x", "Twitter / X"), ("ig", "Instagram")]):
            ToggleRow(plat_card.body, lbl, variable=self.cards_plat_vars[k]).grid(
                row=i, column=0, sticky="ew", pady=3)

        # ── Opciones ──
        opt = Card(scroll, title="Opciones")
        opt.grid(row=3, column=0, sticky="ew", padx=24, pady=(14, 0))
        ob = opt.body

        def _opt_label(text, r):
            ctk.CTkLabel(ob, text=text, text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=11), anchor="w").grid(
                row=r, column=0, sticky="w", pady=7, padx=(0, 12))

        _opt_label("Copias por media:", 0)
        self.cards_copies = Stepper(ob, value=2, min=1, max=50)
        self.cards_copies.grid(row=0, column=1, sticky="w")
        _opt_label("Tema:", 1)
        self.cards_theme = SegmentedControl(ob, ["Oscuro", "Claro"], default="Oscuro")
        self.cards_theme.grid(row=1, column=1, sticky="w")
        _opt_label("Idioma:", 2)
        self.cards_lang = SegmentedControl(ob, ["EN", "ES", "PT"], default="EN")
        self.cards_lang.grid(row=2, column=1, sticky="w")
        _opt_label("Cantidades:", 3)
        self.cards_counts = SegmentedControl(ob, ["Aleatorio", "Manual"],
                                             default="Aleatorio", command=self._cards_toggle_counts)
        self.cards_counts.grid(row=3, column=1, sticky="w")

        self.e_cards_title = ctk.CTkEntry(ob, placeholder_text="Título / tweet / caption (opcional)",
                                          fg_color=BG_INPUT, border_color=BORDER)
        self.e_cards_title.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        self.e_cards_user = ctk.CTkEntry(ob, placeholder_text="Username (opcional)",
                                         fg_color=BG_INPUT, border_color=BORDER)
        self.e_cards_user.grid(row=5, column=0, columnspan=2, sticky="ew", pady=4)

        # manual-count inputs (hidden until "Manual")
        self.cards_manual_frame = ctk.CTkFrame(ob, fg_color="transparent")
        self.cards_manual_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.cards_manual_frame.grid_remove()
        self.cards_count_entries = {}
        manual_fields = [("reddit_votes", "Reddit votos"), ("reddit_comments", "Reddit comentarios"),
                         ("x_likes", "X likes"), ("x_retweets", "X retweets"),
                         ("x_replies", "X replies"), ("x_views", "X views"),
                         ("ig_likes", "IG likes")]
        for i, (key, lbl) in enumerate(manual_fields):
            ctk.CTkLabel(self.cards_manual_frame, text=lbl, text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=10), anchor="w").grid(
                row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 6), pady=3)
            e = ctk.CTkEntry(self.cards_manual_frame, width=110, fg_color=BG_INPUT, border_color=BORDER)
            e.grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", pady=3)
            self.cards_count_entries[key] = e

        # ── Salida ──
        out = Card(scroll, title="Salida")
        out.grid(row=4, column=0, sticky="ew", padx=24, pady=(14, 0))
        out.body.grid_columnconfigure(0, weight=1)
        self.lbl_cards_out = ctk.CTkLabel(out.body, text=self.cards_out_dir, anchor="w",
                                          text_color=TEXT_BODY, font=ctk.CTkFont(size=11))
        self.lbl_cards_out.grid(row=0, column=0, sticky="ew")
        GhostButton(out.body, text="Examinar", command=self.cards_pick_out).grid(row=0, column=1, padx=(8, 0))

        # ── Barra inferior ──
        bar = ctk.CTkFrame(scroll, fg_color="transparent")
        bar.grid(row=5, column=0, sticky="ew", padx=24, pady=(14, 20))
        self.btn_cards_gen = PrimaryButton(bar, text="Generar Tarjetas", command=self.cards_generate)
        self.btn_cards_gen.pack(side="left", padx=(0, 8))
        GhostButton(bar, text="Abrir carpeta", command=self.cards_open_out).pack(side="left")
        self.cards_status = ctk.CTkLabel(bar, text="", text_color=TEXT_MUTED, font=ctk.CTkFont(size=11))
        self.cards_status.pack(side="left", padx=12)

    def _cards_toggle_counts(self, value):
        if value == "Manual":
            self.cards_manual_frame.grid()
        else:
            self.cards_manual_frame.grid_remove()

    def cards_add_media(self):
        paths = filedialog.askopenfilenames(
            title="Selecciona media",
            filetypes=[("Media", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.jpg *.jpeg *.png *.webp"),
                       ("Todos", "*.*")])
        for p in paths:
            if p not in self.cards_media_paths:
                self.cards_media_paths.append(p)
                self.cards_lst.insert(tk.END, os.path.basename(p))

    def cards_remove_media(self):
        for idx in reversed(self.cards_lst.curselection()):
            self.cards_lst.delete(idx)
            del self.cards_media_paths[idx]

    def cards_pick_out(self):
        d = filedialog.askdirectory(title="Carpeta de salida")
        if d:
            self.cards_out_dir = d
            self.lbl_cards_out.configure(text=d)

    def cards_open_out(self):
        if os.path.isdir(self.cards_out_dir):
            os.startfile(self.cards_out_dir)

    def cards_generate(self):
        if not self.cards_media_paths:
            return messagebox.showwarning("⚠️", "Agregá al menos un archivo de media.")
        platforms = [k for k, v in self.cards_plat_vars.items() if v.get()]
        if not platforms:
            return messagebox.showwarning("⚠️", "Seleccioná al menos una plataforma.")

        copies = self.cards_copies.get()
        theme = "light" if self.cards_theme.get() == "Claro" else "dark"
        lang = self.cards_lang.get().lower()
        counts_mode = "manual" if self.cards_counts.get() == "Manual" else "random"

        overrides = {"lang": lang, "counts": counts_mode,
                     "title": self.e_cards_title.get().strip() or None,
                     "username": self.e_cards_user.get().strip() or None}
        if counts_mode == "manual":
            for key, entry in self.cards_count_entries.items():
                raw = entry.get().strip()
                overrides[key] = int(raw) if raw.isdigit() else None

        media = self.cards_media_paths[:]
        out_dir = self.cards_out_dir
        total = len(media) * len(platforms) * copies

        self.btn_cards_gen.configure(state="disabled")
        self.cards_status.configure(text=f"Generando 0/{total}...", text_color=WARNING)

        def task():
            def progress(done, tot):
                self.after(0, lambda d=done, t=tot:
                           self.cards_status.configure(text=f"Generando {d}/{t}..."))
            return self._social_cards.generate_cards(
                media, platforms, copies, theme, overrides, out_dir, progress=progress)

        def done(success, result):
            self.btn_cards_gen.configure(state="normal")
            if success:
                self.cards_status.configure(text=f"✅ {len(result)} tarjetas", text_color=SUCCESS)
                messagebox.showinfo("Tarjetas", f"{len(result)} tarjetas generadas en:\n{out_dir}")
            else:
                self.cards_status.configure(text="❌ Error", text_color=DANGER)
                messagebox.showerror("Error", str(result))

        WorkerThread(self, done, task).start()
```

- [ ] **Step 4: Verify compile**

Run: `python -m py_compile gui_premium_v7.py`
Expected: exit 0, no output.

- [ ] **Step 5: Verify full test suite still green**

Run: `python -m pytest -q`
Expected: PASS — all prior tests plus the new `tests/test_social_cards.py`; no regressions.

- [ ] **Step 6: Commit**

```bash
git add gui_premium_v7.py
git commit -m "feat(ui): social cards generator screen + nav entry"
```

---

### Task 10: Final verification + launch checklist

**Files:** none (verification only).

- [ ] **Step 1: Full suite green**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 2: Compile guard**

Run: `python -m py_compile gui_premium_v7.py social_cards.py`
Expected: exit 0.

- [ ] **Step 3: Scope guard**

Run: `git diff --name-only cb1d77d..HEAD`
Expected: only `social_cards.py`, `tests/test_social_cards.py`, `gui_premium_v7.py`, `requirements.txt`, and the two docs. No changes to `metadata_pool.py`, `database.py`, `videos.py`, `telegram_core.py`, `updater.py`, `Organizador.py`.

- [ ] **Step 4: Produce the manual launch checklist for the user**

The GUI is non-interactive for the agent; hand the user this checklist:

1. Launch the app; sidebar shows **Contenido → 🪪 Tarjetas**.
2. Open Tarjetas; add 1–2 images and 1 short video.
3. Leave all three platforms on, Copias = 2, Tema = Oscuro, Idioma = EN, Cantidades = Aleatorio.
4. Click **Generar Tarjetas**; status counts up; a dialog reports the card count.
5. Click **Abrir carpeta** → `tarjetas_generadas/` holds `reddit_*`, `x_*`, `ig_*` PNGs with the media inside each fake post.
6. Toggle **Cantidades → Manual**, enter a few counts, regenerate → counts appear verbatim on the cards.
7. Switch **Idioma → ES** and **Tema → Claro**, regenerate → Reddit/IG light chrome, Spanish text; X stays dark.
8. Pin a title/username, regenerate → those appear on every card.

---

## Self-Review

**Spec coverage:**
- Standalone module + screen → Tasks 1–9. ✓
- All 3 platforms → Tasks 5–7. ✓
- Static PNG output → Task 8; video-intro remains a documented stretch (not planned — correct). ✓
- Random + pinned overrides → Task 2 + Task 9 wiring. ✓
- Counts random/manual → Task 2 + Task 9 manual frame. ✓
- Languages EN/ES/PT → Task 1 POOLS + Task 2 + Task 9 selector. ✓
- Pure Pillow, procedural icons, font resolver → Tasks 3, 5–7 (documented refinement over the spec's "bundled PNGs/font"; same constraints held). ✓
- Center-crop to fill → Task 4. ✓
- ffmpeg frame grab w/ `_NO_WINDOW` + first-frame fallback → Task 4. ✓
- N×platforms×copies batch + naming → Task 8. ✓
- Worker thread, no GUI freeze → Task 9 `WorkerThread`. ✓
- Pillow in requirements → Task 1. ✓
- Nav under Contenido, no AI-Advisor exposure → Task 9. ✓
- Existing suite stays green → Tasks 9–10. ✓

**Placeholder scan:** No TBD/TODO; every code step carries full code. ✓

**Type consistency:** `build_fields` output keys match what each `render_*` reads; `generate_cards` signature matches the Task 9 call; `WorkerThread(self, done, task)` matches its `__init__(root, callback, task)`. ✓

**Deviation note:** the spec chose *bundled icon PNGs + bundled font*; this plan draws icons procedurally and resolves fonts from system paths. Rationale: an automated implementer cannot source real icon/font binaries; procedural + resolver keeps every hard constraint (pure Pillow, no web, no OOPSIE IP, offline) and is more robust. If pixel-fidelity later demands real assets, swap the `draw_*` helpers and `_load_font` for asset loads without touching callers.
