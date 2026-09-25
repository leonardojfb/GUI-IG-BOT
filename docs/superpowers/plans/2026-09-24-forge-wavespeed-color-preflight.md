# Automatic WaveSpeed Color Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the technical untagged-SDR checkbox and classify recognized WaveSpeed SDR inputs automatically.

**Architecture:** Keep classification in `forge_iphone_profile.py::preflight_batch`; preview and process call the same function. The GUI only displays the classification and blocks genuinely ambiguous sources. No changes to encoding or Legacy MP4.

**Tech Stack:** Python, pytest, ffprobe, CustomTkinter.

## Global Constraints

- Work only in `feature/forge-iphone-profile`; do not modify the original WaveSpeed video or existing tandas.
- Automatic assumption requires all three absent color fields, MP4 WaveSpeed basename pattern, H.264 `yuv420p`, and a parseable `AIGC` JSON object.
- Partial/contradictory tags or missing provenance remain blocked; record the assumption without logging the AIGC payload.
- SDR→HLG remains visually uncalibrated for this generator; recommend iPhone SDR.

---

### Task 1: Classifier

**Files:** Modify `forge_iphone_profile.py`; test `tests/test_forge_iphone_profile.py`.

**Interface:** `preflight_batch(probes: dict[str, dict], profile: str) -> dict` continues to return `counts`, `sources`, `blocked`, `assumptions`.

- [ ] Add a test with an untagged H.264/yuv420p probe, `format.tags.AIGC` set to a JSON object, and a `wavespeed_<hex>.mp4` name. Assert `sources[name] == "sdr"`, no block, and a nonempty assumption for both output profiles.
- [ ] Run `py -m pytest tests/test_forge_iphone_profile.py -k wavespeed -q`; observe the positive test fail because the source is currently unknown.
- [ ] Add negative parametrized tests that independently remove the name pattern, AIGC tag, H.264 codec, 8-bit format, or add one partial color field; all must remain blocked.
- [ ] Implement a small predicate in `forge_iphone_profile.py` using basename regex, codec/pix_fmt, absent triplet, and `json.loads` returning a dict. In `preflight_batch`, apply it only when `classify_color` returned unknown; set the existing assumption field. Remove `known_untagged_sdr` parameter and old manual override.
- [ ] Run the focused tests and commit classifier plus tests.

### Task 2: GUI and documentation

**Files:** Modify `gui_premium_v7.py`, `docs/forge-iphone-profile.md`; test `tests/test_forge_ui.py` and update `tests/test_forge_iphone_profile.py`.

**Interface:** Preview and process both call `preflight_batch(probes, profile_key)`; no checkbox or `forge_untagged_sdr_var` remains.

- [ ] Add a failing GUI source test asserting absence of the checkbox text and variable; assert two preflight call sites without `known_untagged_sdr`.
- [ ] Run `py -m pytest tests/test_forge_ui.py -k untagged -q`; observe failure against current GUI.
- [ ] Remove the checkbox creation and both reads; call `preflight_batch` directly in preview and process. Keep the existing blocked-file error and color counts.
- [ ] Update user documentation: recognized WaveSpeed is automatic, unknown sources block, HLG remains visually uncalibrated.
- [ ] Run focused and Forge/Logística regression tests, plus read-only preflight on the supplied real WaveSpeed MP4. Confirm `git diff --check`; commit.
