"""Small, defensive updater for the local Instagram GUI.

The updater only writes files explicitly allowed by DEFAULT_UPDATEABLE_FILES.
User data stays in the application directory unless a special release manifest
explicitly includes one of the narrow data files below.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable


APP_DIR = Path(__file__).resolve().parent
VERSION_FILE = "version.json"
CONFIG_FILE = "update_config.json"

# Keep this list deliberately narrow. Adding a code file to a release requires
# adding it here and to RELEASE_FILES in build_release.ps1.
DEFAULT_UPDATEABLE_FILES = frozenset(
    {
        "Abrir GUI.bat",
        "Instalar GUI.bat",
        "launch_gui.bat",
        "launcher.py",
        "updater.py",
        "organizador.db",
        "organizador.default.db",
        "version.json",
        "requirements.txt",
        "gui_premium_v7.py",
        "gui_unificada.py",
        "gui_organizador.py",
        "organizador_simple.py",
        "Organizador.py",
        "database.py",
        "organizadortg.py",
        "videos.py",
        "video_editor.py",
        "metadata_pool.py",
        "trial_content.py",
        "telegram_core.py",
        "cleaner.py",
        "vercuentas.py",
        "logo_elittisse.svg",
        "styles/colors.py",
        "styles/components.py",
        "styles/__init__.py",
        "dist_accounts_history.json",
    }
)

_VERSION_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?$")


class UpdateError(RuntimeError):
    """An expected update failure that should not prevent the GUI from opening."""


def _normalise_member(name: str) -> str:
    """Return a safe POSIX-like archive path or raise for traversal attempts."""
    name = name.replace("\\", "/")
    if not name or name.endswith("/") or name.startswith("/"):
        raise UpdateError(f"Entrada no valida en ZIP: {name!r}")
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise UpdateError(f"Ruta insegura en ZIP: {name!r}")
    return "/".join(parts)


def _version_tuple(value: Any) -> tuple[int, int, int]:
    match = _VERSION_RE.fullmatch(str(value).strip())
    if not match:
        raise UpdateError(f"Version invalida: {value!r}")
    return tuple(int(part or 0) for part in match.groups())


def is_newer(remote: Any, local: Any) -> bool:
    return _version_tuple(remote) > _version_tuple(local)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise UpdateError(f"No se pudo leer JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise UpdateError(f"El JSON debe contener un objeto: {path.name}")
    return value


def read_local_version(app_dir: Path = APP_DIR) -> str:
    value = _read_json(app_dir / VERSION_FILE).get("version")
    _version_tuple(value)
    return str(value)


def load_config(app_dir: Path = APP_DIR) -> dict[str, Any]:
    config_path = app_dir / CONFIG_FILE
    if not config_path.exists():
        return {}
    config = _read_json(config_path)
    if config.get("check_on_start", True) is False:
        return {}
    return config


def _request_bytes(
    url: str,
    token: str,
    timeout: int,
    opener: Callable[..., Any] | None = None,
    accept: str | None = None,
) -> bytes:
    if not url:
        raise UpdateError("No hay manifest_url configurada")
    headers = {"User-Agent": "MetodoIG-Updater/1"}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403, 404}:
            raise UpdateError(
                f"GitHub rechazo el acceso ({exc.code}); revisa el token y el permiso Contents: Read-only"
            ) from exc
        raise UpdateError(f"GitHub respondio HTTP {exc.code} al consultar {url}") from exc
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise UpdateError(f"No se pudo consultar {url}") from exc


def _download_to_file(
    url: str,
    destination: Path,
    token: str,
    timeout: int,
    opener: Callable[..., Any] | None = None,
    accept: str | None = None,
) -> None:
    destination.write_bytes(_request_bytes(url, token, timeout, opener, accept))


def _github_asset_url(
    manifest: dict[str, Any],
    token: str,
    timeout: int,
    opener: Callable[..., Any] | None = None,
) -> str | None:
    """Resolve a private GitHub release asset to its authenticated API URL."""
    repository = str(manifest.get("github_repository", "")).strip()
    release_tag = str(manifest.get("github_release_tag", "")).strip()
    asset_name = str(manifest.get("asset_name", "")).strip()
    if not any((repository, release_tag, asset_name)):
        return None
    if not all((repository, release_tag, asset_name)):
        raise UpdateError("El manifiesto de GitHub esta incompleto")
    if not token:
        raise UpdateError("Falta el token de GitHub para consultar el repositorio privado")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise UpdateError("github_repository no tiene un formato valido")

    release_url = f"https://api.github.com/repos/{repository}/releases/tags/{release_tag}"
    try:
        release = json.loads(
            _request_bytes(
                release_url,
                token,
                timeout,
                opener,
                "application/vnd.github+json",
            ).decode("utf-8")
        )
    except json.JSONDecodeError as exc:
        raise UpdateError("GitHub devolvio una release invalida") from exc
    if not isinstance(release, dict) or not isinstance(release.get("assets"), list):
        raise UpdateError("No se encontro la release de GitHub")
    for asset in release["assets"]:
        if isinstance(asset, dict) and asset.get("name") == asset_name:
            asset_url = str(asset.get("url", "")).strip()
            if asset_url:
                return asset_url
    raise UpdateError(f"No se encontro el archivo {asset_name} en la release de GitHub")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_files(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, str]]:
    files: list[tuple[zipfile.ZipInfo, str]] = []
    for info in archive.infolist():
        if info.is_dir() or info.filename.endswith(("/", "\\")):
            continue
        relative = _normalise_member(info.filename)
        # ZIP symlinks can escape the target directory after extraction.
        unix_mode = (info.external_attr >> 16) & 0o170000
        if unix_mode == 0o120000:
            raise UpdateError(f"No se permiten enlaces simbolicos en ZIP: {relative}")
        files.append((info, relative))
    return files


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.update-tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def apply_package(
    app_dir: Path,
    package_path: Path,
    manifest: dict[str, Any],
    allowed_files: Iterable[str] = DEFAULT_UPDATEABLE_FILES,
) -> str:
    """Apply a verified package transactionally and return its version."""
    app_dir = Path(app_dir).resolve()
    allowed = {item.replace("\\", "/") for item in allowed_files}
    remote_version = str(manifest.get("version", ""))
    _version_tuple(remote_version)
    local_version = read_local_version(app_dir)
    if not is_newer(remote_version, local_version):
        return local_version

    with tempfile.TemporaryDirectory(prefix="metodo_ig_update_") as temp_name:
        extract_dir = Path(temp_name) / "package"
        backup_dir = Path(temp_name) / "backup"
        extract_dir.mkdir()
        backup_dir.mkdir()
        backups: list[tuple[Path, Path]] = []
        created: list[Path] = []

        try:
            with zipfile.ZipFile(package_path) as archive:
                entries = _archive_files(archive)
                manifest_files = manifest.get("files")
                requested = (
                    {str(item).replace("\\", "/") for item in manifest_files}
                    if isinstance(manifest_files, list)
                    else allowed
                )
                selected = [
                    (info, relative)
                    for info, relative in entries
                    if relative in allowed and relative in requested
                ]
                if not any(relative == VERSION_FILE for _, relative in selected):
                    raise UpdateError("El ZIP no contiene version.json")

                for info, relative in selected:
                    target = extract_dir / Path(relative)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, target.open("wb") as destination:
                        shutil.copyfileobj(source, destination)

            packaged_version = read_local_version(extract_dir)
            if packaged_version != remote_version:
                raise UpdateError(
                    f"Version del ZIP ({packaged_version}) distinta del manifiesto ({remote_version})"
                )

            for file_name in sorted(
                relative for _, relative in selected if relative != VERSION_FILE
            ) + [VERSION_FILE]:
                source = extract_dir / Path(file_name)
                target = app_dir / Path(file_name)
                if target.exists():
                    backup = backup_dir / Path(file_name)
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup)
                    backups.append((target, backup))
                else:
                    created.append(target)
                _atomic_copy(source, target)
        except Exception as exc:
            for target in created:
                try:
                    target.unlink()
                except FileNotFoundError:
                    pass
            for target, backup in reversed(backups):
                try:
                    _atomic_copy(backup, target)
                except OSError:
                    pass
            if isinstance(exc, UpdateError):
                raise
            raise UpdateError("No se pudo aplicar la actualizacion; se restauro la version anterior") from exc

    return remote_version


def check_and_apply(
    app_dir: Path = APP_DIR,
    opener: Callable[..., Any] | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> bool:
    """Check the configured manifest and apply it; failures are non-fatal."""
    app_dir = Path(app_dir).resolve()

    def report(message: str) -> None:
        print(f"Actualizador: {message}")
        if status_callback:
            status_callback(message)

    try:
        config = load_config(app_dir)
        manifest_url = str(config.get("manifest_url", "")).strip()
        if not manifest_url:
            report("manifest_url no configurada; se abre la app local.")
            return False
        timeout = int(config.get("timeout_seconds", 15))
        token = str(config.get("access_token", "")) or os.getenv("IG_GUI_UPDATE_TOKEN", "")
        manifest = json.loads(_request_bytes(manifest_url, token, timeout, opener).decode("utf-8-sig"))
        if not isinstance(manifest, dict):
            raise UpdateError("El manifiesto remoto no es un objeto JSON")
        remote_version = str(manifest.get("version", ""))
        local_version = read_local_version(app_dir)
        if not is_newer(remote_version, local_version):
            report(f"ya esta instalada la version {local_version}.")
            return False

        github_asset_url = _github_asset_url(manifest, token, timeout, opener)
        package_url = github_asset_url or str(manifest.get("url", "")).strip()
        expected_hash = str(manifest.get("sha256", "")).strip().lower()
        if not package_url or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise UpdateError("El manifiesto necesita una URL y sha256 valido")
        with tempfile.TemporaryDirectory(prefix="metodo_ig_download_") as temp_name:
            package_path = Path(temp_name) / "release.zip"
            _download_to_file(
                package_url,
                package_path,
                token,
                timeout,
                opener,
                "application/octet-stream" if github_asset_url else None,
            )
            actual_hash = sha256_file(package_path)
            if actual_hash != expected_hash:
                raise UpdateError("El SHA-256 del ZIP no coincide con el manifiesto")
            new_version = apply_package(app_dir, package_path, manifest)
        report(f"aplicacion actualizada a {new_version}.")
        return True
    except Exception as exc:
        message = f"{exc}. Se abrira la version local."
        print(f"Actualizador: {message}", file=sys.stderr)
        if status_callback:
            status_callback(message)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Actualizador de Metodo IG VIDEOS")
    parser.add_argument("--check-and-apply", action="store_true")
    args = parser.parse_args()
    if args.check_and_apply:
        check_and_apply()
        return 0
    parser.error("Usa --check-and-apply")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
