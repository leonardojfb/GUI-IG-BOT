# Airtable Published Video Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Globally exclude source videos explicitly marked published in Telegram, using Airtable as the only persistent authority.

**Architecture:** The desktop sender computes each source SHA-256 and gets the published hash set from Airtable before topic creation. A compact base64url version of that hash travels in the Telegram button callback. Railway validates it, upserts Airtable, then marks the message.

**Tech Stack:** Python 3.14, hashlib, requests, Airtable Web API, Telegram Bot API, Railway, pytest.

## Global Constraints

- Airtable table \`Videos publicados\` is the only publication store; add neither JSON nor SQLite state.
- Identity is SHA-256 of original source bytes: renamed files match; any bytes/metadata change is eligible.
- The exclusion is global across every account, tanda, calendar, and topic.
- Airtable read/write failure is fail-closed: no send and no visual published mark.
- Keep legacy \`pub\` buttons visual-only. New buttons are \`pub:<base64url-sha256>\`.
- Never log Airtable tokens or raw remote response bodies.

---

## File Structure

- \`airtable_sync.py\`: published hash reader using the existing desktop config.
- \`organizadortg.py\`: source hash, callback value, filtering and reporting.
- \`railway_telegram_publish_webhook/telegram_publish_webhook.py\`: callback parser and Airtable upsert.
- \`tests/test_airtable_sync.py\`, \`tests/test_telegram_express_parallel.py\`: desktop contract tests.
- \`railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py\`: webhook tests.
- \`railway_telegram_publish_webhook/README.md\`, \`README.txt\`: configuration and live proof.

### Task 1: Read the global published-hash set

**Files:**

- Modify: \`airtable_sync.py:13-24, 475-510\`
- Modify: \`tests/test_airtable_sync.py:1-112\`

**Interfaces:**

- Consumes: \`AirtableConfig(personal_access_token, base_id, table_name)\`.
- Produces: \`fetch_published_video_hashes(config, requests_get=requests.get) -> set[str]\`.
- Raises: \`AirtableSyncError("No se pudo descargar los videos publicados de Airtable.")\`.

- [ ] **Step 1: Write failing adapter tests**

\`\`\`python
def test_fetch_published_hashes_uses_dedicated_table_and_all_pages():
    calls = []
    def fake_get(url, *, headers, params, timeout):
        calls.append((url, params.copy()))
        if params.get("offset"):
            return FakeResponse({"records": [{"id": "rec2", "fields": {"SHA-256": "b" * 64}}]})
        return FakeResponse({"records": [{"id": "rec1", "fields": {"SHA-256": "a" * 64}}], "offset": "next"})
    assert fetch_published_video_hashes(AirtableConfig("pat", "app123", "Cuentas"), fake_get) == {"a" * 64, "b" * 64}
    assert calls[0][0] == "https://api.airtable.com/v0/app123/Videos%20publicados"

def test_fetch_published_hashes_rejects_invalid_hash():
    with pytest.raises(AirtableSyncError, match="videos publicados"):
        fetch_published_video_hashes(AirtableConfig("pat", "app123", "Cuentas"), lambda **_: FakeResponse({"records": [{"id": "rec", "fields": {"SHA-256": "wrong"}}]}))
\`\`\`

- [ ] **Step 2: Verify RED**

Run: \`py -m pytest tests/test_airtable_sync.py -k published_hashes -v\`

Expected: FAIL because the adapter does not exist.

- [ ] **Step 3: Implement the minimal paginated reader**

\`\`\`python
PUBLISHED_VIDEOS_TABLE = "Videos publicados"

def fetch_published_video_hashes(config: AirtableConfig, requests_get: Callable[..., Any] = requests.get) -> set[str]:
    url = "https://api.airtable.com/v0/{}/{}".format(quote(config.base_id, safe=""), quote(PUBLISHED_VIDEOS_TABLE, safe=""))
    hashes, offset = set(), None
    while True:
        params = {"pageSize": 100, **({"offset": offset} if offset else {})}
        try:
            response = requests_get(url, headers=_airtable_headers(config), params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise AirtableSyncError("No se pudo descargar los videos publicados de Airtable.") from exc
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise AirtableSyncError("Airtable devolvió videos publicados inválidos.")
        for record in records:
            value = (record.get("fields") or {}).get("SHA-256") if isinstance(record, dict) else None
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise AirtableSyncError("Airtable devolvió videos publicados inválidos.")
            hashes.add(value)
        offset = payload.get("offset")
        if not offset:
            return hashes
\`\`\`

Import \`re\`; do not change account schema preparation or mirroring.

- [ ] **Step 4: Verify GREEN**

Run: \`py -m pytest tests/test_airtable_sync.py -k published_hashes -v\`

Expected: PASS for pagination, malformed remote values, and transport failure.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add -- airtable_sync.py tests/test_airtable_sync.py
git commit -m "feat: read published video hashes from Airtable"
\`\`\`

### Task 2: Filter before Telegram topics or delivery

**Files:**

- Modify: \`organizadortg.py:1-20, 125-131, 949-1190\`
- Modify: \`tests/test_telegram_express_parallel.py:1-90\`

**Interfaces:**

- Consumes: \`fetch_published_video_hashes(load_airtable_config())\`.
- Produces: \`_source_sha256(path: str) -> str\`, \`_published_callback_data(source_hash: str) -> str\`.
- Returns: \`❌ No se pudo verificar Airtable; no se enviaron videos.\` before any topic on lookup/hash failure.

- [ ] **Step 1: Write failing behavior tests**

\`\`\`python
def test_plan_omits_identical_published_bytes_for_every_account(monkeypatch, tmp_path):
    old, new = tmp_path / "old.mp4", tmp_path / "new.mp4"
    old.write_bytes(b"same"); new.write_bytes(b"different")
    calls, sent = _stub_common_telegram_plan(monkeypatch, [
        _video(old, "alpha"), _video(old, "beta", "renamed.mp4"), _video(new, "beta")], _two_accounts())
    monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object())
    monkeypatch.setattr(organizadortg, "fetch_published_video_hashes", lambda _cfg: {organizadortg._source_sha256(old)})
    result = organizadortg.execute_telegram_plan(datetime(2026, 8, 14))
    assert [item[3] for item in sent] == [str(new)]
    assert "Omitidos publicados: 2" in result

def test_plan_fails_closed_before_topic_creation_on_airtable_error(monkeypatch, tmp_path):
    calls, sent = _stub_common_telegram_plan(monkeypatch, [_video(tmp_path / "x.mp4", "alpha")], _one_account())
    monkeypatch.setattr(organizadortg, "load_airtable_config", lambda: object())
    monkeypatch.setattr(organizadortg, "fetch_published_video_hashes", lambda _cfg: (_ for _ in ()).throw(AirtableSyncError("down")))
    assert organizadortg.execute_telegram_plan(datetime(2026, 8, 14)) == "❌ No se pudo verificar Airtable; no se enviaron videos."
    assert calls == [] and sent == []
\`\`\`

Add \`_video\`, \`_one_account\`, and \`_two_accounts\` helpers inside this test module; each video has \`path\`, \`filename\`, \`category\`, \`day\`, and \`username\`.

- [ ] **Step 2: Verify RED**

Run: \`py -m pytest tests/test_telegram_express_parallel.py -k "published or closed" -v\`

Expected: FAIL because no Airtable read or exclusion occurs.

- [ ] **Step 3: Implement hash-aware jobs**

\`\`\`python
def _source_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(_windows_long_path(path), "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _published_callback_data(source_hash: str) -> str:
    return "pub:" + base64.urlsafe_b64encode(bytes.fromhex(source_hash)).decode("ascii").rstrip("=")
\`\`\`

Extend \`_publish_button_markup(caption=None, source_hash=None)\` and \`_send_video_to_topic(..., source_hash=None)\` while retaining \`pub\` when no hash is supplied. Immediately after \`scan_calendar_structure()\` succeeds, load Airtable hashes and assign \`vid["source_hash"]\`; retain only unmatched videos. Do this before \`load_json\`, topic creation, or \`sendMessage\`. Pass the hash through each job to \`_send_video_to_topic\`. Catch \`AirtableSyncError\`, \`OSError\`, and \`ValueError\`; return the exact fail-closed text. Return \`✨ PROCESO TERMINADO. Se enviaron {global_sent} videos. Omitidos publicados: {omitted_published}.\`.

- [ ] **Step 4: Verify GREEN and regressions**

Run: \`py -m pytest tests/test_telegram_express_parallel.py tests/test_telegram_long_paths.py tests/test_telegram_single_account_selection.py -v\`

Expected: PASS; duplicate bytes never enter sender, a changed file is sent, and legacy markup remains supported.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add -- organizadortg.py tests/test_telegram_express_parallel.py tests/test_telegram_long_paths.py
git commit -m "feat: skip globally published Telegram videos"
\`\`\`

### Task 3: Persist new callbacks before Telegram marking

**Files:**

- Modify: \`railway_telegram_publish_webhook/telegram_publish_webhook.py:1-180\`
- Modify: \`railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py:1-180\`

**Interfaces:**

- Consumes: \`pub:<43-char-base64url-sha256>\` and Railway \`AIRTABLE_PAT\`, \`AIRTABLE_BASE_ID\`, \`AIRTABLE_PUBLISHED_TABLE\`.
- Produces: \`published_hash_from_callback(data: str) -> str | None\`, \`upsert_published_video(fields: dict) -> bool\`.
- Writes: Airtable \`performUpsert\` keyed only by \`SHA-256\`.

- [ ] **Step 1: Write failing webhook tests**

\`\`\`python
def test_hash_callback_upserts_before_caption_edit(monkeypatch):
    calls, stored = [], []
    monkeypatch.setattr(webhook, "upsert_published_video", lambda fields: stored.append(fields) or True)
    monkeypatch.setattr(webhook, "post_telegram_method", lambda _t, method, payload: calls.append((method, payload)) or {"ok": True})
    assert webhook.handle_update(_callback(_hash_callback(b"a" * 32)), "token")["handled"]
    assert stored[0]["SHA-256"] == "a" * 64
    assert calls[-1][0] == "editMessageCaption"

def test_hash_callback_leaves_button_when_airtable_write_fails(monkeypatch):
    calls = []
    monkeypatch.setattr(webhook, "upsert_published_video", lambda _fields: False)
    monkeypatch.setattr(webhook, "post_telegram_method", lambda _t, method, payload: calls.append((method, payload)) or {"ok": True})
    webhook.handle_update(_callback(_hash_callback(b"a" * 32)), "token")
    assert not any(method.startswith("editMessage") for method, _ in calls)

def test_legacy_pub_remains_visual_only(monkeypatch):
    monkeypatch.setattr(webhook, "upsert_published_video", lambda _fields: pytest.fail("legacy must not write"))
    assert webhook.handle_update(_callback("pub"), "token")["handled"]
\`\`\`

\`_hash_callback\` must use \`base64.urlsafe_b64encode(raw).decode().rstrip("=")\`; \`_callback\` must include \`video.file_name\`, chat/message IDs, caption, and markup.

- [ ] **Step 2: Verify RED**

Run: \`py -m pytest railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py -v\`

Expected: FAIL because no callback parser/upsert exists.

- [ ] **Step 3: Implement strict parsing and idempotent remote write**

\`\`\`python
def published_hash_from_callback(data: str) -> str | None:
    match = re.fullmatch(r"pub:([A-Za-z0-9_-]{43})", str(data or ""))
    if not match:
        return None
    try:
        raw = base64.urlsafe_b64decode(match.group(1) + "=")
    except (ValueError, binascii.Error):
        return None
    return raw.hex() if len(raw) == 32 else None

def upsert_published_video(fields: dict) -> bool:
    token, base_id = os.environ.get("AIRTABLE_PAT", ""), os.environ.get("AIRTABLE_BASE_ID", "")
    table = os.environ.get("AIRTABLE_PUBLISHED_TABLE", "Videos publicados")
    if not token or not base_id:
        return False
    payload = {"records": [{"fields": fields}], "performUpsert": {"fieldsToMergeOn": ["SHA-256"]}}
    url = f"https://api.airtable.com/v0/{urllib.parse.quote(base_id, safe='')}/{urllib.parse.quote(table, safe='')}"
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="PATCH",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return bool((json.loads(response.read().decode("utf-8"))).get("records"))
    except Exception as exc:
        print(f"Airtable publication upsert failed: {type(exc).__name__}", file=sys.stderr, flush=True)
        return False
\`\`\`

Use \`urllib.request\` with a 15-second timeout. Catch exceptions, log only exception class, and return false. On a new valid callback, call the upsert before \`answerCallbackQuery\` or edit. Fields are \`SHA-256\`, \`Archivo original\` from \`message.video.file_name\`, \`Chat ID\`, \`Message ID\`, and \`Marcado por\` when Telegram supplied a username. On false, answer \`No se pudo guardar; intenta de nuevo.\` and leave caption/markup unchanged. Keep the current literal \`pub\` flow unchanged.

- [ ] **Step 4: Verify GREEN**

Run: \`py -m pytest railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py -v\`

Expected: PASS; upsert happens before edit, failure preserves the button, malformed data does not write, and legacy messages are visual-only.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add -- railway_telegram_publish_webhook/telegram_publish_webhook.py railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py
git commit -m "feat: persist Telegram publications in Airtable"
\`\`\`

### Task 4: Document setup and prove the deployed chain

**Files:**

- Create: \`railway_telegram_publish_webhook/README.md\`
- Modify: \`README.txt:68-74\`
- Modify: \`railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py\`

- [ ] **Step 1: Write the failing setup-document test**

\`\`\`python
def test_readme_requires_publication_store_variables():
    text = Path("railway_telegram_publish_webhook/README.md").read_text(encoding="utf-8")
    for value in ("AIRTABLE_PAT", "AIRTABLE_BASE_ID", "AIRTABLE_PUBLISHED_TABLE", "SHA-256"):
        assert value in text
\`\`\`

- [ ] **Step 2: Verify RED**

Run: \`py -m pytest railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py -k readme -v\`

Expected: FAIL because README is absent.

- [ ] **Step 3: Add exact operator requirements**

Write the README with these instructions: create \`Videos publicados\` in the current Airtable base with primary single-line text \`SHA-256\`; add optional \`Archivo original\`, \`Chat ID\`, \`Message ID\`, \`Marcado por\`; give desktop PAT read scope and Railway PAT read/write scope; set Railway variables \`AIRTABLE_PAT\`, \`AIRTABLE_BASE_ID\`, optional \`AIRTABLE_PUBLISHED_TABLE=Videos publicados\`; never put the Railway PAT in \`airtable_config.json\`. Update \`README.txt\` to say Airtable is authoritative for Telegram resend blocking.

- [ ] **Step 4: Run final local gates**

Run: \`py -m pytest tests/test_airtable_sync.py tests/test_telegram_express_parallel.py tests/test_telegram_long_paths.py tests/test_telegram_single_account_selection.py railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py -v\`

Expected: PASS.

Run: \`py -m py_compile airtable_sync.py organizadortg.py railway_telegram_publish_webhook/telegram_publish_webhook.py\`

Expected: exit code 0.

- [ ] **Step 5: Commit and perform the live boundary**

\`\`\`powershell
git add -- README.txt railway_telegram_publish_webhook/README.md railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py
git commit -m "docs: explain Airtable publication guard setup"
\`\`\`

Deploy Railway, send one non-production video, press \`Publicado\`, confirm exactly one Airtable row, rerun delivery, and confirm an omitted count with no duplicate send. Report this separately from local tests.
