import importlib
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from tests.support.e2e_audit import audit_database, audit_filesystem, audit_manifest_calendar, audit_telegram, render_audit_report
from tests.support.fake_telegram import FakeTelegramSender

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / "tests" / "fixtures" / "e2e_pipeline_matrix.json"
APP_MODULES = [
    "Organizador",
    "airtable_sync",
    "calendar_manifest",
    "cleaner",
    "console_encoding",
    "database",
    "gui_organizador",
    "gui_unificada",
    "launcher",
    "metadata_pool",
    "organizadortg",
    "render_performance",
    "social_publishing",
    "telegram_core",
    "trial_content",
    "updater",
    "vercuentas",
    "video_editor",
    "videos",
]


def load_matrix(path: str | Path = MATRIX_PATH) -> dict:
    matrix = json.loads(Path(path).read_text(encoding="utf-8"))
    assert matrix["categories"] == ["PRUEBA_CAT_A", "PRUEBA_CAT_B", "PRUEBA_CAT_C"]
    assert [va["name"] for va in matrix["vas"]] == ["PRUEBA_VA_A", "PRUEBA_VA_B", "PRUEBA_VA_C"]
    assert sorted(matrix["tandas"]) == ["ED_A", "ED_B", "ED_C", "FO_A", "FO_B", "FO_C", "TA_A", "TA_B", "TA_C"]
    return matrix


def make_run_root() -> Path:
    run_id = "e2e-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    root = Path(tempfile.gettempdir()) / "ig_gui_e2e_pipeline" / run_id
    root.mkdir(parents=True, exist_ok=False)
    return root


def _release_files_from_build_script() -> list[str]:
    script = (REPO_ROOT / "build_release.ps1").read_text(encoding="utf-8")
    match = re.search(r"\$ReleaseFiles\s*=\s*@\((.*?)\)", script, re.S)
    if not match:
        raise AssertionError("build_release.ps1 must define a $ReleaseFiles array")
    return re.findall(r'"([^"]+)"', match.group(1))


def _make_release_zip(package_root: Path) -> Path:
    zip_path = package_root / "MetodoIG-e2e.zip"
    with ZipFile(zip_path, "w") as archive:
        for relative in _release_files_from_build_script():
            source = REPO_ROOT / relative
            if not source.is_file():
                raise AssertionError(f"release file missing: {relative}")
            archive.write(source, relative)
    return zip_path


def _extract_release_install(package_root: Path) -> Path:
    zip_path = _make_release_zip(package_root)
    install_root = package_root / "install"
    install_root.mkdir()
    with ZipFile(zip_path) as archive:
        archive.extractall(install_root)
    return install_root


@contextmanager
def _app_import_context(app_root: Path | None):
    if app_root is None:
        yield
        return

    app_root = Path(app_root).resolve()
    saved_path = list(os.sys.path)
    saved_modules = {name: os.sys.modules.get(name) for name in APP_MODULES}
    for name in APP_MODULES:
        os.sys.modules.pop(name, None)
    os.sys.path.insert(0, str(app_root))
    importlib.invalidate_caches()
    try:
        yield
    finally:
        for name in APP_MODULES:
            os.sys.modules.pop(name, None)
            if saved_modules[name] is not None:
                os.sys.modules[name] = saved_modules[name]
        os.sys.path[:] = saved_path
        importlib.invalidate_caches()


def _run_extracted_launcher_smoke(install_root: Path) -> dict:
    script = install_root / "_launcher_smoke.py"
    script.write_text(
        "\n".join(
            [
                "import json",
                "from types import SimpleNamespace",
                "import launcher",
                "opened = []",
                "launcher._run_update_check = lambda: True",
                "launcher._ensure_timezone_data = lambda: ''",
                "launcher._ensure_pillow = lambda: ''",
                "launcher.subprocess.Popen = lambda command, **kwargs: opened.append((command, kwargs)) or SimpleNamespace(pid=1234)",
                "returncode = launcher.main()",
                "payload = {'returncode': returncode, 'opened_gui': bool(opened), 'gui_path': opened[0][0][1] if opened else ''}",
                "print(json.dumps(payload))",
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [os.sys.executable, str(script)],
        cwd=str(install_root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-1600:] or result.stdout[-1600:] or "launcher smoke failed")
    return json.loads(result.stdout.strip())


def sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-1600:] or result.stdout[-1600:] or f"command failed: {cmd}")


def create_video(path: Path, color: str, marker: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    draw = f"drawtext=text='{marker}':x=20:y=40:fontcolor=white:fontsize=24"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=320x568:d=0.35:r=15",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-vf",
        draw,
        "-shortest",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-metadata",
        f"title={marker}",
        str(path),
    ]
    try:
        _run(cmd)
    except RuntimeError:
        cmd = [part for part in cmd if part not in ["-vf", draw]]
        _run(cmd)


def create_photo(path: Path, color: str, marker: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=120x120",
            "-frames:v",
            "1",
            str(path),
        ]
    )


def create_captions(path: Path, label: str) -> None:
    tags = {
        "CAPTION_ED_A_UNIQUE": "#ed_a_one #ed_a_two",
        "CAPTION_TA_B_UNIQUE": "#ta_b_one #ta_b_two",
        "CAPTION_FO_C_UNIQUE": "#fo_c_one #fo_c_two",
    }[label]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{label}\nSecond line for {label}\n{tags}\n", encoding="utf-8")


def seed_database(db_path: str | Path, matrix: dict) -> None:
    import database

    old_path = database.DB_PATH
    database.DB_PATH = str(db_path)
    db = database.DatabaseManager()
    try:
        for category in matrix["categories"]:
            db.add_category(category)
        for va in matrix["vas"]:
            db.add_va(va["name"])
            db.update_va_telegram_group(va["name"], va["telegram_id"])
        for account in matrix["accounts"]:
            try:
                db.add_virtual_account(account["username"], account["category"])
            except sqlite3.IntegrityError:
                pass
            db.update_account(account["username"], assigned_va=account["va"])
        for va in matrix["vas"]:
            for category in matrix["categories"]:
                db.set_schedule_config(va["name"], category.lower(), 0, ["8:00 AM", "1:00 PM", "7:00 PM"])
    finally:
        db.close()
        database.DB_PATH = old_path


def _clone_db(run_root: Path, app_root: Path | None = None) -> Path:
    source_root = Path(app_root) if app_root is not None else REPO_ROOT
    src = source_root / "organizador.db"
    dst = run_root / "organizador.db"
    if src.exists():
        shutil.copy2(src, dst)
    return dst


@contextmanager
def patched_modules(run_root: Path):
    import database
    import metadata_pool
    import Organizador
    import organizadortg
    import video_editor
    import videos

    saved = {
        "database.DB_PATH": database.DB_PATH,
        "videos.FOLDER_INPUTS": videos.FOLDER_INPUTS,
        "videos.FOLDER_OUTPUT_ROOT": videos.FOLDER_OUTPUT_ROOT,
        "videos.RES_W": videos.RES_W,
        "videos.RES_H": videos.RES_H,
        "videos.FPS": videos.FPS,
        "Organizador.base_dir": Organizador.base_dir,
        "Organizador.source_root": Organizador.source_root,
        "Organizador.output_root": Organizador.output_root,
        "organizadortg.input_root": organizadortg.input_root,
        "organizadortg.base_dir": organizadortg.base_dir,
        "organizadortg.db": organizadortg.db,
    }
    database.DB_PATH = str(run_root / "organizador.db")
    videos.FOLDER_INPUTS = str(run_root / "inputs")
    videos.FOLDER_OUTPUT_ROOT = str(run_root / "videos_finales")
    videos.RES_W = 320
    videos.RES_H = 568
    videos.FPS = "15"
    Organizador.base_dir = str(run_root)
    Organizador.source_root = str(run_root / "videos_finales")
    Organizador.output_root = str(run_root / "CALENDARIO_POSTEO")
    organizadortg.input_root = str(run_root / "CALENDARIO_POSTEO")
    organizadortg.base_dir = str(run_root)
    try:
        organizadortg.db.close()
    except Exception:
        pass
    organizadortg.db = database.DatabaseManager()
    try:
        yield database, videos, video_editor, metadata_pool, Organizador, organizadortg
    finally:
        try:
            organizadortg.db.close()
        except Exception:
            pass
        database.DB_PATH = saved["database.DB_PATH"]
        videos.FOLDER_INPUTS = saved["videos.FOLDER_INPUTS"]
        videos.FOLDER_OUTPUT_ROOT = saved["videos.FOLDER_OUTPUT_ROOT"]
        videos.RES_W = saved["videos.RES_W"]
        videos.RES_H = saved["videos.RES_H"]
        videos.FPS = saved["videos.FPS"]
        Organizador.base_dir = saved["Organizador.base_dir"]
        Organizador.source_root = saved["Organizador.source_root"]
        Organizador.output_root = saved["Organizador.output_root"]
        organizadortg.input_root = saved["organizadortg.input_root"]
        organizadortg.base_dir = saved["organizadortg.base_dir"]
        # NOT `organizadortg.db = saved["organizadortg.db"]`: that object was
        # already .close()'d a few lines above (it's the same connection this
        # context manager closed on entry, before swapping in the run_root
        # one) -- restoring it just hands back a dead connection. Any test
        # that runs after this context manager in the same process would
        # inherit a module-level organizadortg.db that raises
        # "Cannot operate on a closed database." the moment it's queried.
        # Reopen fresh against the now-restored database.DB_PATH instead.
        organizadortg.db = database.DatabaseManager()


def _db_add_tanda(db_path: Path, name: str, p1: str, p2: str, captions: str | None) -> None:
    import database

    old = database.DB_PATH
    database.DB_PATH = str(db_path)
    db = database.DatabaseManager()
    try:
        db.add_tanda(name, p1, p2, captions or "")
    finally:
        db.close()
        database.DB_PATH = old


def _record_output(manifest, tanda, path: Path, source_hash=None, extra=None):
    manifest["outputs"].append(
        {
            "tanda": tanda,
            "output": str(path),
            "output_name": path.name,
            "source_hash": source_hash,
            "output_hash": sha256_file(path),
            "metadata": extra or {},
        }
    )


def _create_edicion(run_root, matrix, manifest, video_editor):
    colors = {"ED_A": "red", "ED_B": "blue", "ED_C": "green"}
    photo_colors = {"ED_A": "yellow", "ED_B": "white", "ED_C": "magenta"}
    for tanda in ["ED_A", "ED_B", "ED_C"]:
        out_dir = run_root / "videos_finales" / tanda
        out_dir.mkdir(parents=True, exist_ok=True)
        photo = run_root / "inputs" / f"{tanda}_PHOTO.png"
        create_photo(photo, photo_colors[tanda], f"{tanda}_PHOTO")
        photo_hash = sha256_file(photo)
        for index in range(1, 4):
            source = run_root / "inputs" / tanda / f"{tanda}_SOURCE_{index}.mp4"
            create_video(source, colors[tanda], f"{tanda}_SOURCE_{index}")
            output = out_dir / f"{tanda}__{tanda}_P1_{index}__{tanda}_P2_{index}.mp4"
            overlay = {
                "photo": str(photo),
                "position": "center",
                "x": 0,
                "y": 0,
                "size": 35,
                "ratio": "1:1",
                "frame": index,
                "duration_ms": 250,
                "opacity": 85,
            }
            video_editor.render_video(str(source), str(output), [overlay])
            _record_output(manifest, tanda, output, sha256_file(source), {"photo_hash": photo_hash, "frame": index})


def _create_tandas(run_root, db_path, matrix, manifest, videos):
    colors = {"TA_A": "purple", "TA_B": "orange", "TA_C": "cyan"}
    for tanda in ["TA_A", "TA_B", "TA_C"]:
        p1_folder = f"{tanda}_P1"
        p2_folder = f"{tanda}_P2"
        p1 = run_root / "inputs" / p1_folder / f"{tanda}_P1ID.mp4"
        create_video(p1, colors[tanda], f"{tanda}_P1ID")
        for index in range(1, 4):
            p2 = run_root / "inputs" / p2_folder / f"{tanda}_P2ID_{index}.mp4"
            create_video(p2, colors[tanda], f"{tanda}_P2ID_{index}")
        _db_add_tanda(db_path, tanda, p1_folder, p2_folder, None)
        videos.render_tanda(tanda)
        for output in sorted((run_root / "videos_finales" / tanda).glob("*.mp4")):
            _record_output(manifest, tanda, output, sha256_file(p1), {"p1_folder": p1_folder, "p2_folder": p2_folder})


def _create_forge(run_root, db_path, manifest, database, metadata_pool):
    source_map = {
        "FO_A": sorted((run_root / "videos_finales" / "ED_A").glob("*.mp4"))[0],
        "FO_B": sorted((run_root / "videos_finales" / "TA_B").glob("*.mp4"))[0],
        "FO_C": sorted((run_root / "videos_finales" / "ED_C").glob("*.mp4"))[0],
    }
    configs = {
        "FO_A": ("Default", "Default", None, None),
        "FO_B": ("Custom", "Custom", {"crop": True, "mirror": True}, {"crop": (2, 6)}),
        "FO_C": ("Alto", "Light", None, None),
    }
    db = database.DatabaseManager()
    try:
        metas = metadata_pool.generate_unique_metadata(db, 9)
        meta_index = 0
        for tanda, source in source_map.items():
            effect_level, strength_level, fx_vars, overrides = configs[tanda]
            enabled = metadata_pool.efectos_to_enabled(effect_level, fx_vars)
            strength = metadata_pool.fuerza_to_strength(strength_level, 50)
            out_dir = run_root / "videos_finales" / tanda
            out_dir.mkdir(parents=True, exist_ok=True)
            source_hash = sha256_file(source)
            for copy_index in range(1, 4):
                output = out_dir / f"{source.stem}__c{copy_index:02d}.mp4"
                meta = metas[meta_index]
                meta_index += 1
                params = metadata_pool.apply_variant_and_metadata(
                    str(source),
                    str(output),
                    meta,
                    rng=random.Random(260726 + meta_index),
                    enabled=enabled,
                    strength=strength,
                    overrides=overrides,
                )
                out_hash = sha256_file(output)
                db.save_forge_video(tanda, source.name, output.name, out_hash)
                saved_meta = dict(meta)
                saved_meta["video_hash"] = out_hash
                db.save_metadata_fingerprints([saved_meta])
                _record_output(
                    manifest,
                    tanda,
                    output,
                    source_hash,
                    {"source": str(source), "effects": effect_level, "strength": strength_level, "params": params},
                )
            _db_add_tanda(db_path, tanda, tanda, tanda, "")
    finally:
        db.close()


def _create_captions(run_root):
    caption_dir = run_root / "captions"
    create_captions(caption_dir / "CAP_ED_A.txt", "CAPTION_ED_A_UNIQUE")
    create_captions(caption_dir / "CAP_TA_B.txt", "CAPTION_TA_B_UNIQUE")
    create_captions(caption_dir / "CAP_FO_C.txt", "CAPTION_FO_C_UNIQUE")
    return caption_dir


def _register_non_tanda_outputs(db_path, matrix, run_root):
    for tanda in ["ED_A", "ED_B", "ED_C", "FO_A", "FO_B", "FO_C"]:
        _db_add_tanda(db_path, tanda, tanda, tanda, None)


def _assign_logistica_captions(db_path, matrix, run_root):
    import database

    previous_db_path = database.DB_PATH
    database.DB_PATH = str(db_path)
    db = database.DatabaseManager()
    try:
        for tanda, info in matrix["tandas"].items():
            caption = info.get("caption")
            db.set_tanda_captions(tanda, str(run_root / "captions" / caption) if caption else None)
    finally:
        db.close()
        database.DB_PATH = previous_db_path


def _distribute_all(run_root, matrix, Organizador):
    previews = {}
    results = {}
    calendar = run_root / "CALENDARIO_POSTEO"
    if calendar.exists():
        shutil.rmtree(calendar)
    pairs = [(name, info["category"]) for name, info in matrix["tandas"].items()]
    for tanda, category in pairs:
        previews[tanda] = Organizador.preview_distribution_tanda(tanda, category, 1, False, "1")
        random.seed(260726)
        results[tanda] = Organizador.distribute_tanda(tanda, category, 1, False, "1")
    return previews, results


def _run_two_tanda_route(run_root, db_path, matrix):
    second_root = run_root / "two_tanda_route"
    shutil.copytree(run_root / "videos_finales", second_root / "videos_finales")
    shutil.copy2(db_path, second_root / "organizador.db")
    with patched_modules(second_root) as mods:
        Organizador = mods[4]
        random.seed(260726)
        result = Organizador.distribute_tanda("ED_A", "PRUEBA_CAT_A", 1, False, "1", tanda_name_2="FO_A")
        files = list((second_root / "CALENDARIO_POSTEO").rglob("*.mp4"))
        return {"result": result, "count": len(files), "files": [str(p) for p in files]}


def _run_telegram(organizadortg, selected_accounts):
    fake = FakeTelegramSender()
    saved = {
        "call_tg": organizadortg.call_tg,
        "get_or_create_topic": organizadortg.get_or_create_topic,
        "_send_video_to_topic": organizadortg._send_video_to_topic,
        "sleep": organizadortg.time.sleep,
    }
    organizadortg.call_tg = fake.fake_call
    organizadortg.get_or_create_topic = fake.fake_get_or_create_topic
    organizadortg._send_video_to_topic = fake.fake_send_video
    organizadortg.time.sleep = lambda seconds: None
    try:
        result = organizadortg.execute_telegram_plan(datetime(2026, 7, 26), selected_accounts=selected_accounts)
    finally:
        organizadortg.call_tg = saved["call_tg"]
        organizadortg.get_or_create_topic = saved["get_or_create_topic"]
        organizadortg._send_video_to_topic = saved["_send_video_to_topic"]
        organizadortg.time.sleep = saved["sleep"]
    return result, fake.events


def _snapshot_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        snapshot = {}
        for table in ["account_categories", "virtual_assistants", "virtual_accounts", "batch_tandas", "schedule_config"]:
            cur.execute(f"SELECT * FROM {table}")
            snapshot[table] = [dict(row) for row in cur.fetchall()]
        return snapshot
    finally:
        conn.close()


def _write_test_report(summary, findings, audit_json, audit_md):
    report_dir = REPO_ROOT / "docs" / "test-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "2026-07-26-e2e-multimedia-logistica-telegram.md"
    fail_counts = {}
    for finding in findings:
        fail_counts[finding["code"]] = fail_counts.get(finding["code"], 0) + 1
    lines = [
        "# E2E multimedia Logistica Telegram",
        "",
        f"- run_id: {summary['run_id']}",
        f"- run_root: {summary['run_root']}",
        f"- audit_json: {audit_json}",
        f"- audit_md: {audit_md}",
        f"- processed_outputs: {summary['actual']['processed_outputs']} / {summary['expected']['processed_outputs']}",
        f"- distributed_files: {summary['actual']['distributed_files']} / {summary['expected']['distributed_files']}",
        f"- manifest_entries: {summary['actual']['manifest_entries']} / {summary['expected']['manifest_entries']}",
        f"- telegram_sends: {summary['actual']['telegram_sends']} / {summary['expected']['telegram_sends']}",
        "",
        "## Finding counts",
        "",
    ]
    for code, count in sorted(fail_counts.items()):
        lines.append(f"- {code}: {count}")
    lines.extend(
        [
            "",
            "## Bugs",
            "",
            "| status | code | tanda | account | VA | caption expected | caption actual | file |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for finding in findings:
        lines.append(
            "| {status} | {code} | {tanda} | {account} | {va} | {ce} | {ca} | {file} |".format(
                status=finding.get("status", ""),
                code=finding.get("code", ""),
                tanda=finding.get("tanda", ""),
                account=finding.get("account_actual", ""),
                va=finding.get("va_actual", ""),
                ce=str(finding.get("caption_expected", "")),
                ca=str(finding.get("caption_actual", ""))[:80].replace("\n", " "),
                file=finding.get("file", ""),
            )
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(report_path)


def run_e2e_pipeline(keep_artifacts=True, app_root: str | Path | None = None):
    app_root = Path(app_root) if app_root is not None else None
    with _app_import_context(app_root):
        matrix = load_matrix()
        run_root = make_run_root()
        db_path = _clone_db(run_root, app_root)
        seed_database(db_path, matrix)
        captions_dir = _create_captions(run_root)
        manifest = {
            "run_id": run_root.name,
            "run_root": str(run_root),
            "matrix": matrix,
            "outputs": [],
            "accounts_by_username": {a["username"]: a for a in matrix["accounts"]},
            "va_chat_by_name": {v["name"]: v["telegram_id"] for v in matrix["vas"]},
            "initial_db_snapshot": _snapshot_db(db_path),
        }

        with patched_modules(run_root) as mods:
            database, videos, video_editor, metadata_pool, Organizador, organizadortg = mods
            _create_edicion(run_root, matrix, manifest, video_editor)
            _create_tandas(run_root, db_path, matrix, manifest, videos)
            _create_forge(run_root, db_path, manifest, database, metadata_pool)
            _register_non_tanda_outputs(db_path, matrix, run_root)
            _assign_logistica_captions(db_path, matrix, run_root)
            previews, dist_results = _distribute_all(run_root, matrix, Organizador)
            two_tanda = _run_two_tanda_route(run_root, db_path, matrix)
            try:
                organizadortg.db.close()
            except Exception:
                pass
            organizadortg.db = database.DatabaseManager()
            selected_accounts = [a["username"] for a in matrix["accounts"]]
            telegram_result, telegram_events = _run_telegram(organizadortg, selected_accounts)

        manifest["sha256"] = sha256_file
        current_manifest_path = run_root / "calendar_manifest.json"
        if current_manifest_path.exists():
            current_manifest = json.loads(current_manifest_path.read_text(encoding="utf-8"))
            manifest["calendar_entries"] = current_manifest.get("entries", [])
        else:
            manifest["calendar_entries"] = []
        calendar_files = list((run_root / "CALENDARIO_POSTEO").rglob("*.mp4"))
        findings = []
        findings.extend(
            audit_filesystem(
                manifest,
                run_root / "videos_finales",
                run_root / "CALENDARIO_POSTEO",
                require_calendar_files=False,
            )
        )
        findings.extend(audit_manifest_calendar(manifest))
        findings.extend(audit_database(manifest, db_path))
        findings.extend(audit_telegram(manifest, telegram_events, "captions_by_tanda"))

        actual = {
            "processed_outputs": len(manifest["outputs"]),
            "distributed_files": len(calendar_files),
            "manifest_entries": len(manifest["calendar_entries"]),
            "telegram_sends": len([e for e in telegram_events if e.get("event") == "video"]),
            "categories": matrix["categories"],
            "vas": [v["name"] for v in matrix["vas"]],
            "tandas": list(matrix["tandas"].keys()),
        }
        expected = {
            "processed_outputs": 27,
            "distributed_files": 0,
            "manifest_entries": 9,
            "telegram_sends": 9,
        }
        summary = {
            "run_id": run_root.name,
            "run_root": str(run_root),
            "expected": expected,
            "actual": actual,
            "previews": previews,
            "distribution_results": dist_results,
            "two_tanda_route": two_tanda,
            "telegram_results": {
                "captions_by_tanda": telegram_result,
            },
        }
        audit_json, audit_md = render_audit_report(findings, run_root / "audit.md", summary)
        test_report = _write_test_report(summary, findings, audit_json, audit_md)
        manifest["final_db_snapshot"] = _snapshot_db(db_path)
        write_manifest(run_root / "manifest.json", {k: v for k, v in manifest.items() if k != "sha256"})
        result = dict(summary)
        result.update({"findings": findings, "audit_json": audit_json, "audit_md": audit_md, "test_report": test_report})
        if not keep_artifacts:
            shutil.rmtree(run_root, ignore_errors=True)
        return result


def run_extracted_release_e2e_pipeline(keep_artifacts=True):
    package_root = make_run_root()
    install_root = _extract_release_install(package_root)
    launcher_result = _run_extracted_launcher_smoke(install_root)
    result = run_e2e_pipeline(keep_artifacts=keep_artifacts, app_root=install_root)
    result["install_root"] = str(install_root)
    result["launcher"] = launcher_result
    if not keep_artifacts:
        shutil.rmtree(package_root, ignore_errors=True)
    return result


def run_clean_runtime_smoke():
    package_root = make_run_root()
    install_root = _extract_release_install(package_root)
    venv_root = package_root / ".venv-clean"
    subprocess.run(
        [os.sys.executable, "-m", "venv", str(venv_root)],
        cwd=str(install_root),
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    python = venv_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(install_root / "requirements.txt"),
        ],
        cwd=str(install_root),
        check=True,
        capture_output=True,
        text=True,
        timeout=240,
    )

    modules = [
        "airtable_sync",
        "calendar_manifest",
        "console_encoding",
        "database",
        "gui_premium_v7",
        "launcher",
        "metadata_pool",
        "Organizador",
        "organizadortg",
        "render_performance",
        "social_publishing",
        "telegram_core",
        "trial_content",
        "updater",
        "video_editor",
        "videos",
    ]
    script = install_root / "_clean_runtime_smoke.py"
    script.write_text(
        "\n".join(
            [
                "import importlib, json, sys",
                "from types import SimpleNamespace",
                f"modules = {modules!r}",
                "imported = []",
                "for name in modules:",
                "    importlib.import_module(name)",
                "    imported.append(name)",
                "import launcher",
                "opened = []",
                "launcher._run_update_check = lambda: True",
                "launcher._ensure_timezone_data = lambda: ''",
                "launcher._ensure_pillow = lambda: ''",
                "launcher.subprocess.Popen = lambda command, **kwargs: opened.append((command, kwargs)) or SimpleNamespace(pid=1234)",
                "returncode = launcher.main()",
                "print(json.dumps({'venv': sys.prefix != sys.base_prefix, 'imported': imported, 'launcher_returncode': returncode, 'opened_gui': bool(opened)}))",
            ]
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    result = subprocess.run(
        [str(python), str(script)],
        cwd=str(install_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-1600:] or result.stdout[-1600:] or "clean runtime smoke failed")
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    shutil.rmtree(package_root, ignore_errors=True)
    return payload
