"""Lectura y conciliación unidireccional de cuentas desde Airtable."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import json
import re
from urllib.parse import quote

import requests


CONFIG_FILE = Path(__file__).with_name("airtable_config.json")
PUBLISHED_VIDEOS_TABLE = "Videos publicados"


def published_wavespeed_family_key(filename: str | None) -> str | None:
    """Identify a WaveSpeed source across Forge copies when legacy origin is absent."""
    name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    match = re.fullmatch(r"(wavespeed_[0-9a-f]{32})__c\d+\.(?:mp4|mov)", name, re.IGNORECASE)
    return "source-family:" + match.group(1).lower() if match else None
MANAGED_FIELDS = (
    "username",
    "two_factor",
    "assigned_va",
    "account_type",
    "trials_active",
    "account_day",
    "social_network",
    "vpn_proxy",
    "account_link",
)


@dataclass(frozen=True)
class AirtableRequiredField:
    name: str
    field_type: str


AIRTABLE_ACCOUNT_COLUMNS = (
    AirtableRequiredField("Username", "singleLineText"),
    AirtableRequiredField("2FA", "multilineText"),
    AirtableRequiredField("VA", "singleLineText"),
    AirtableRequiredField("Categoria", "singleLineText"),
    AirtableRequiredField("Trials desbloqueados", "checkbox"),
    AirtableRequiredField("Dia", "singleLineText"),
    AirtableRequiredField("Red social", "singleLineText"),
    AirtableRequiredField("VPN / Proxy", "multilineText"),
    AirtableRequiredField("Link", "url"),
)
AIRTABLE_FIELD_OPTIONS = {
    "Trials desbloqueados": {"icon": "check", "color": "greenBright"},
}


class AirtableSyncError(Exception):
    """Error que puede mostrarse al usuario sin revelar secretos."""


@dataclass(frozen=True)
class AirtableConfig:
    personal_access_token: str = field(repr=False)
    base_id: str
    table_name: str


@dataclass(frozen=True)
class AirtableSchemaPreparation:
    added_fields: tuple[str, ...]
    incompatible_fields: tuple[tuple[str, str, str], ...]
    source_renames: tuple[tuple[str, str], ...] = ()
    backup_renames: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class AirtableColumnRepairPlan:
    source_renames: tuple[tuple[str, str], ...]
    backup_renames: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class AirtableLegacyMigrationPlan:
    updates: list[dict[str, Any]]
    field_counts: dict[str, int]

    @property
    def records_to_update(self) -> int:
        return len(self.updates)


@dataclass(frozen=True)
class AirtableAccount:
    username: str
    two_factor: str = field(repr=False)
    assigned_va: str = "Sin Asignar"
    account_type: str = ""
    trials_active: bool = False
    account_day: str = ""
    social_network: str = ""
    vpn_proxy: str = field(default="", repr=False)
    account_link: str = ""

    def as_managed_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in MANAGED_FIELDS}


@dataclass(frozen=True)
class AccountSyncPlan:
    create: list[dict[str, Any]]
    update: list[dict[str, Any]]
    delete_usernames: list[str]
    categories_to_add: list[str]

    @property
    def changed(self) -> bool:
        return bool(self.create or self.update or self.delete_usernames)


@dataclass(frozen=True)
class AirtableMirrorPlan:
    create: list[dict[str, Any]]
    update: list[dict[str, Any]]
    delete: list[dict[str, str]]

    @property
    def changed(self) -> bool:
        return bool(self.create or self.update or self.delete)


def normalize_username(value: Any) -> str:
    return str(value or "").strip().lstrip("@").strip()


def _text(fields: dict[str, Any], name: str, default: str = "") -> str:
    value = fields.get(name, default)
    if isinstance(value, list):
        if len(value) > 1:
            raise AirtableSyncError(f"'{name}' debe tener un solo valor por cuenta.")
        value = value[0] if value else default
    if isinstance(value, dict):
        raise AirtableSyncError(f"'{name}' debe ser texto por cuenta.")
    return str(value or default).strip()


def _checkbox(fields: dict[str, Any], name: str) -> bool:
    value = fields.get(name, False)
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    if isinstance(value, str):
        return value.strip().casefold() in {"si", "sí", "true", "1"}
    raise AirtableSyncError(f"'{name}' debe ser un checkbox.")


def _account_from_record(record: dict[str, Any]) -> AirtableAccount:
    fields = record.get("fields") or {}
    if not isinstance(fields, dict):
        raise AirtableSyncError("Airtable devolvió una fila inválida.")
    username = normalize_username(fields.get("Username"))
    account_type = _text(fields, "Categoria")
    if not username:
        raise AirtableSyncError("Cada fila debe tener Username.")
    if not account_type:
        raise AirtableSyncError(f"La cuenta @{username} no tiene Categoria.")
    return AirtableAccount(
        username=username,
        two_factor=_text(fields, "2FA"),
        assigned_va=_text(fields, "VA", "Sin Asignar") or "Sin Asignar",
        account_type=account_type,
        trials_active=_checkbox(fields, "Trials desbloqueados"),
        account_day=_text(fields, "Dia"),
        social_network=_text(fields, "Red social"),
        vpn_proxy=_text(fields, "VPN / Proxy"),
        account_link=_text(fields, "Link"),
    )


def load_airtable_config(path: str | Path = CONFIG_FILE) -> AirtableConfig:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AirtableSyncError("No se pudo leer la configuración de Airtable.") from exc
    config = AirtableConfig(
        personal_access_token=str(raw.get("personal_access_token", "")).strip(),
        base_id=str(raw.get("base_id", "")).strip(),
        table_name=str(raw.get("table_name", "")).strip(),
    )
    if not all((config.personal_access_token, config.base_id, config.table_name)):
        raise AirtableSyncError("La configuración de Airtable está incompleta.")
    return config


def save_airtable_config(config: AirtableConfig, path: str | Path = CONFIG_FILE) -> None:
    if not all((config.personal_access_token.strip(), config.base_id.strip(), config.table_name.strip())):
        raise AirtableSyncError("Completa token, Base ID y nombre de tabla.")
    Path(path).write_text(
        json.dumps(
            {
                "personal_access_token": config.personal_access_token,
                "base_id": config.base_id,
                "table_name": config.table_name,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _airtable_headers(config: AirtableConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.personal_access_token}"}


def _configured_table_schema(
    config: AirtableConfig,
    requests_get: Callable[..., Any],
) -> dict[str, Any]:
    url = "https://api.airtable.com/v0/meta/bases/{}/tables".format(
        quote(config.base_id, safe="")
    )
    try:
        response = requests_get(url, headers=_airtable_headers(config), timeout=20)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise AirtableSyncError(
            "No se pudo leer la estructura de Airtable. Verifica que el token tenga schema.bases:read."
        ) from exc
    tables = payload.get("tables") if isinstance(payload, dict) else None
    if not isinstance(tables, list):
        raise AirtableSyncError("Airtable devolvió una estructura de base inválida.")
    for table in tables:
        if isinstance(table, dict) and table.get("name") == config.table_name:
            if not isinstance(table.get("id"), str) or not isinstance(table.get("fields"), list):
                raise AirtableSyncError("Airtable devolvió una tabla inválida.")
            return table
    raise AirtableSyncError(
        f"La tabla '{config.table_name}' no existe en la base indicada. Créala en Airtable e inténtalo otra vez."
    )


def fetch_airtable_table_schema(
    config: AirtableConfig,
    requests_get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """Lee el esquema de la tabla configurada sin modificar Airtable."""
    return _configured_table_schema(config, requests_get)


def _airtable_error_code(response: Any) -> str:
    """Devuelve solo el tipo de error público de Airtable, nunca el cuerpo ni token."""
    try:
        payload = response.json()
        code = payload.get("error", {}).get("type", "") if isinstance(payload, dict) else ""
    except Exception:
        return ""
    return code if isinstance(code, str) and code.replace("_", "").isalnum() else ""


LEGACY_AIRTABLE_FIELD_MAPPING = (
    ("Field 1", "2FA"),
    ("Field 2", "VA"),
    ("Field 3", "Categoria"),
    ("Field 4", "Trials desbloqueados"),
    ("Field 5", "Dia"),
    ("Field 6", "Red social"),
    ("Field 7", "VPN / Proxy"),
    ("Field 8", "Link"),
)


def _is_populated(value: Any) -> bool:
    return value not in (None, "", [], False)


def _legacy_trial_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return True if value else None
    normalized = str(value or "").strip().casefold()
    if normalized in {"si", "sí", "true", "1"}:
        return True
    return None


def _legacy_link_value(value: Any) -> str:
    link = str(value or "").strip()
    if link and not link.casefold().startswith(("http://", "https://")):
        return f"https://{link}"
    return link


LEGACY_COLUMN_RENAMES = (
    ("Field 1", "2FA"),
    ("Field 2", "VA"),
    ("Field 3", "Categoria"),
    ("Field 4", "Trials desbloqueados"),
    ("Field 5", "Dia"),
    ("Field 6", "Red social"),
    ("Field 7", "VPN / Proxy"),
    ("Field 8", "Link"),
)


def build_legacy_column_repair_plan(table: dict[str, Any]) -> AirtableColumnRepairPlan:
    fields = table.get("fields") if isinstance(table, dict) else None
    if not isinstance(fields, list):
        raise AirtableSyncError("Airtable devolvió una tabla inválida.")
    by_name = {
        field.get("name"): field
        for field in fields
        if isinstance(field, dict) and isinstance(field.get("name"), str)
    }
    if not all(source in by_name for source, _target in LEGACY_COLUMN_RENAMES):
        return AirtableColumnRepairPlan((), ())
    source_names = {source for source, _target in LEGACY_COLUMN_RENAMES}
    backups: list[tuple[str, str]] = []
    for _source, target in LEGACY_COLUMN_RENAMES:
        existing = by_name.get(target)
        if existing is None or target in source_names:
            continue
        backup_name = f"__backup__{target}"
        suffix = 2
        while backup_name in by_name:
            backup_name = f"__backup__{target}_{suffix}"
            suffix += 1
        backups.append((str(existing["id"]), backup_name))
        by_name[backup_name] = existing
    sources = tuple((str(by_name[source]["id"]), target) for source, target in LEGACY_COLUMN_RENAMES)
    return AirtableColumnRepairPlan(sources, tuple(backups))


def build_positional_column_repair_plan(table: dict[str, Any]) -> AirtableColumnRepairPlan:
    """Renombra las primeras nueve columnas, sin inspeccionar sus nombres actuales."""
    fields = table.get("fields") if isinstance(table, dict) else None
    if not isinstance(fields, list):
        raise AirtableSyncError("Airtable devolvió una tabla inválida.")
    targets = tuple(required.name for required in AIRTABLE_ACCOUNT_COLUMNS)
    if len(fields) < len(targets):
        raise AirtableSyncError(
            f"La tabla debe tener al menos {len(targets)} columnas para aplicar el formato de cuentas."
        )
    first_fields = fields[: len(targets)]
    for field_item in first_fields:
        if not isinstance(field_item, dict) or not field_item.get("id"):
            raise AirtableSyncError("Airtable devolvió una columna inválida.")

    # Airtable exige nombres únicos durante cada PATCH. Si una columna fuera
    # de las primeras nueve ya usa uno de los nombres destino, la apartamos
    # temporalmente para que el renombrado posicional no falle.
    desired_ids = {str(field_item["id"]): index for index, field_item in enumerate(first_fields)}
    used_names = {
        str(field_item.get("name"))
        for field_item in fields
        if isinstance(field_item, dict) and isinstance(field_item.get("name"), str)
    }
    backups: list[tuple[str, str]] = []
    for index, field_item in enumerate(fields):
        if not isinstance(field_item, dict):
            continue
        current_name = field_item.get("name")
        field_id = str(field_item.get("id") or "")
        if current_name not in targets or desired_ids.get(field_id) == targets.index(current_name):
            continue
        backup_name = f"__backup__{current_name}"
        suffix = 2
        while backup_name in used_names:
            backup_name = f"__backup__{current_name}_{suffix}"
            suffix += 1
        backups.append((field_id, backup_name))
        used_names.add(backup_name)

    source_renames = tuple(
        (str(field_item["id"]), target)
        for field_item, target in zip(first_fields, targets)
        if field_item.get("name") != target
    )
    return AirtableColumnRepairPlan(source_renames, tuple(backups))


def build_legacy_field_migration_plan(records: list[dict[str, Any]]) -> AirtableLegacyMigrationPlan:
    """Copia el formato genérico legado sin borrar ni sobrescribir datos de Airtable."""
    updates: list[dict[str, Any]] = []
    field_counts: dict[str, int] = {}
    for record in records:
        record_id = record.get("id")
        fields = record.get("fields") or {}
        if not isinstance(record_id, str) or not isinstance(fields, dict):
            raise AirtableSyncError("Airtable devolvió una fila inválida para migrar.")
        update_fields: dict[str, Any] = {}
        for source_name, target_name in LEGACY_AIRTABLE_FIELD_MAPPING:
            source_value = fields.get(source_name)
            if not _is_populated(source_value) or _is_populated(fields.get(target_name)):
                continue
            if target_name == "Trials desbloqueados":
                target_value = _legacy_trial_value(source_value)
                if target_value is None:
                    continue
            elif target_name == "Link":
                target_value = _legacy_link_value(source_value)
            else:
                target_value = source_value
            update_fields[target_name] = target_value
            field_counts[target_name] = field_counts.get(target_name, 0) + 1
        if update_fields:
            updates.append({"id": record_id, "fields": update_fields})
    return AirtableLegacyMigrationPlan(updates, field_counts)


def prepare_airtable_account_table(
    config: AirtableConfig,
    requests_get: Callable[..., Any] = requests.get,
    requests_post: Callable[..., Any] = requests.post,
    requests_patch: Callable[..., Any] = requests.patch,
) -> AirtableSchemaPreparation:
    """Renombra por posición las primeras nueve columnas de una tabla existente."""
    table = _configured_table_schema(config, requests_get)
    repair = build_positional_column_repair_plan(table)
    fields_url = "https://api.airtable.com/v0/meta/bases/{}/tables/{}/fields/{}"
    for field_id, new_name in [*repair.backup_renames, *repair.source_renames]:
        url = fields_url.format(
            quote(config.base_id, safe=""), quote(table["id"], safe=""), quote(field_id, safe="")
        )
        response = None
        try:
            response = requests_patch(
                url,
                headers={**_airtable_headers(config), "Content-Type": "application/json"},
                json={"name": new_name},
                timeout=20,
            )
            response.raise_for_status()
        except Exception as exc:
            status_code = getattr(response, "status_code", None)
            diagnostic = f"HTTP {status_code}" if isinstance(status_code, int) else "HTTP desconocido"
            error_code = _airtable_error_code(response) if response is not None else ""
            if error_code:
                diagnostic = f"{diagnostic}: {error_code}"
            raise AirtableSyncError(
                f"No se pudo renombrar la columna a '{new_name}'. Airtable rechazó el cambio ({diagnostic})."
            ) from exc
    return AirtableSchemaPreparation(
        added_fields=(),
        incompatible_fields=(),
        source_renames=repair.source_renames,
        backup_renames=repair.backup_renames,
    )


def fetch_airtable_accounts(
    config: AirtableConfig,
    requests_get: Callable[..., Any] = requests.get,
) -> list[AirtableAccount]:
    url = "https://api.airtable.com/v0/{}/{}".format(
        quote(config.base_id, safe=""), quote(config.table_name, safe="")
    )
    headers = _airtable_headers(config)
    offset: str | None = None
    seen: set[str] = set()
    accounts: list[AirtableAccount] = []

    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        try:
            response = requests_get(url, headers=headers, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise AirtableSyncError(
                "No se pudo descargar Airtable. Verifica conexión, token, Base ID y tabla."
            ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("records", []), list):
            raise AirtableSyncError("Airtable devolvió una respuesta inválida.")
        for record in payload["records"]:
            if isinstance(record, dict) and record.get("fields") == {}:
                continue
            account = _account_from_record(record)
            key = account.username.casefold()
            if key in seen:
                raise AirtableSyncError(f"Username duplicado en Airtable: @{account.username}.")
            seen.add(key)
            accounts.append(account)
        offset = payload.get("offset")
        if not offset:
            return accounts


def fetch_airtable_records(
    config: AirtableConfig,
    requests_get: Callable[..., Any] = requests.get,
) -> list[dict[str, Any]]:
    """Descarga los registros crudos conservando sus IDs para el espejo remoto."""
    url = "https://api.airtable.com/v0/{}/{}".format(
        quote(config.base_id, safe=""), quote(config.table_name, safe="")
    )
    headers = _airtable_headers(config)
    offset: str | None = None
    records: list[dict[str, Any]] = []
    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        try:
            response = requests_get(url, headers=headers, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise AirtableSyncError(
                "No se pudo descargar Airtable. Verifica conexión, token, Base ID y tabla."
            ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("records", []), list):
            raise AirtableSyncError("Airtable devolvió una respuesta inválida.")
        for record in payload["records"]:
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                raise AirtableSyncError("Airtable devolvió un registro inválido.")
            records.append(record)
        offset = payload.get("offset")
        if not offset:
            return records


def fetch_published_video_hashes(
    config: AirtableConfig,
    requests_get: Callable[..., Any] = requests.get,
) -> set[str]:
    """Devuelve los SHA-256 publicados desde la tabla global de Airtable."""
    url = "https://api.airtable.com/v0/{}/{}".format(
        quote(config.base_id, safe=""), quote(PUBLISHED_VIDEOS_TABLE, safe="")
    )
    hashes: set[str] = set()
    offset: str | None = None
    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        try:
            response = requests_get(
                url, headers=_airtable_headers(config), params=params, timeout=20
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise AirtableSyncError(
                "No se pudo descargar los videos publicados de Airtable."
            ) from exc
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise AirtableSyncError("Airtable devolvió videos publicados inválidos.")
        for record in records:
            fields = record.get("fields") if isinstance(record, dict) else None
            value = fields.get("SHA-256") if isinstance(fields, dict) else None
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise AirtableSyncError("Airtable devolvió videos publicados inválidos.")
            hashes.add(value)
        offset = payload.get("offset")
        if not offset:
            return hashes


def fetch_published_video_origins(
    config: AirtableConfig,
    requests_get: Callable[..., Any] = requests.get,
) -> set[str]:
    """Devuelve los tokens de origin publicados desde Airtable."""
    url = "https://api.airtable.com/v0/{}/{}".format(
        quote(config.base_id, safe=""), quote(PUBLISHED_VIDEOS_TABLE, safe="")
    )
    origins: set[str] = set()
    offset: str | None = None
    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        try:
            response = requests_get(
                url, headers=_airtable_headers(config), params=params, timeout=20
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise AirtableSyncError(
                "No se pudo descargar los origins publicados de Airtable."
            ) from exc
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise AirtableSyncError("Airtable devolvió origins publicados inválidos.")
        for record in records:
            fields = record.get("fields") if isinstance(record, dict) else None
            value = fields.get("Origin token") if isinstance(fields, dict) else None
            if value is None:
                continue
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16}", value):
                raise AirtableSyncError("Airtable devolvió origins publicados inválidos.")
            origins.add(value)
        offset = payload.get("offset")
        if not offset:
            return origins


def fetch_published_video_publications(
    config: AirtableConfig,
    requests_get: Callable[..., Any] = requests.get,
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Return account-scoped publications; rows without an account are ignored."""
    url = "https://api.airtable.com/v0/{}/{}".format(
        quote(config.base_id, safe=""), quote(PUBLISHED_VIDEOS_TABLE, safe="")
    )
    hashes: set[tuple[str, str]] = set()
    origins: set[tuple[str, str]] = set()
    offset: str | None = None
    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        try:
            response = requests_get(
                url, headers=_airtable_headers(config), params=params, timeout=20
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise AirtableSyncError(
                "No se pudieron descargar las publicaciones por cuenta de Airtable."
            ) from exc
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise AirtableSyncError("Airtable devolvió publicaciones por cuenta inválidas.")
        for record in records:
            fields = record.get("fields") if isinstance(record, dict) else None
            if not isinstance(fields, dict):
                raise AirtableSyncError("Airtable devolvió publicaciones por cuenta inválidas.")
            account_id = str(fields.get("Account ID") or "").strip()
            if not account_id:
                continue
            if not re.fullmatch(r"\d+", account_id):
                raise AirtableSyncError("Airtable devolvió publicaciones por cuenta inválidas.")
            source_hash = fields.get("SHA-256")
            if source_hash is not None:
                if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
                    raise AirtableSyncError("Airtable devolvió publicaciones por cuenta inválidas.")
                hashes.add((account_id, source_hash))
            origin_token = fields.get("Origin token")
            if origin_token is not None:
                if not isinstance(origin_token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16}", origin_token):
                    raise AirtableSyncError("Airtable devolvió publicaciones por cuenta inválidas.")
                origins.add((account_id, origin_token))
            else:
                family_key = published_wavespeed_family_key(fields.get("Archivo original"))
                if family_key:
                    origins.add((account_id, family_key))
        offset = payload.get("offset")
        if not offset:
            return hashes, origins


def _coerce_managed_row(row: AirtableAccount | dict[str, Any]) -> dict[str, Any]:
    values = row.as_managed_dict() if isinstance(row, AirtableAccount) else dict(row)
    username = normalize_username(values.get("username"))
    account_type = str(values.get("account_type") or "").strip()
    if not username or not account_type:
        raise AirtableSyncError("Cada cuenta necesita Username y Categoria.")
    return {
        "username": username,
        "two_factor": str(values.get("two_factor") or "").strip(),
        "assigned_va": str(values.get("assigned_va") or "Sin Asignar").strip() or "Sin Asignar",
        "account_type": account_type,
        "trials_active": bool(values.get("trials_active")),
        "account_day": str(values.get("account_day") or "").strip(),
        "social_network": str(values.get("social_network") or "").strip(),
        "vpn_proxy": str(values.get("vpn_proxy") or "").strip(),
        "account_link": str(values.get("account_link") or "").strip(),
    }


def _airtable_fields_from_managed_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convierte una cuenta local al formato exacto de las nueve columnas."""
    return {
        "Username": row["username"],
        "2FA": row["two_factor"],
        "VA": row["assigned_va"],
        "Categoria": row["account_type"],
        "Trials desbloqueados": row["trials_active"],
        "Dia": row["account_day"],
        "Red social": row["social_network"],
        "VPN / Proxy": row["vpn_proxy"],
        "Link": row["account_link"],
    }


def _airtable_fields_for_schema(
    fields: dict[str, Any],
    table_schema: dict[str, Any],
    username: str,
) -> dict[str, Any]:
    """Adapta los nueve campos al tipo y opciones actuales de Airtable."""
    schema_fields = table_schema.get("fields") if isinstance(table_schema, dict) else None
    if not isinstance(schema_fields, list):
        raise AirtableSyncError("Airtable devolvió un esquema de columnas inválido.")
    by_name = {
        item.get("name"): item
        for item in schema_fields
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    adapted: dict[str, Any] = {}
    for name, value in fields.items():
        field = by_name.get(name)
        if field is None:
            raise AirtableSyncError(f"@{username}: Airtable no tiene la columna '{name}'.")
        field_type = field.get("type")
        if field_type == "singleSelect":
            choices = (field.get("options") or {}).get("choices", [])
            choice_names = [
                choice.get("name")
                for choice in choices
                if isinstance(choice, dict) and isinstance(choice.get("name"), str)
            ]
            if name == "Trials desbloqueados":
                desired = {"sí", "si", "yes", "true", "1"} if bool(value) else {"no", "false", "0"}
                selected = next((choice for choice in choice_names if choice.casefold() in desired), None)
            else:
                normalized = str(value or "").strip()
                if not normalized:
                    continue
                selected = next((choice for choice in choice_names if choice.casefold() == normalized.casefold()), None)
            if selected is None:
                raise AirtableSyncError(
                    f"@{username}: '{name}' no acepta el valor '{value}'. "
                    f"Opciones: {', '.join(choice_names)}."
                )
            adapted[name] = selected
        elif field_type == "url":
            normalized = str(value or "").strip()
            if normalized:
                adapted[name] = normalized
        else:
            adapted[name] = value
    return adapted


def build_airtable_mirror_plan(
    local_rows: list[dict[str, Any]],
    remote_records: list[dict[str, Any]],
    table_schema: dict[str, Any] | None = None,
) -> AirtableMirrorPlan:
    """Construye un espejo completo local -> Airtable por Username."""
    local_by_key: dict[str, dict[str, Any]] = {}
    for raw_row in local_rows:
        row = _coerce_managed_row(raw_row)
        key = row["username"].casefold()
        if key in local_by_key:
            raise AirtableSyncError(f"Username duplicado en la GUI: @{row['username']}.")
        local_by_key[key] = row

    remote_by_key: dict[str, tuple[str, dict[str, Any]]] = {}
    for record in remote_records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise AirtableSyncError("Airtable devolvió un registro inválido.")
        account = _account_from_record(record)
        row = account.as_managed_dict()
        key = row["username"].casefold()
        if key in remote_by_key:
            raise AirtableSyncError(f"Username duplicado en Airtable: @{row['username']}.")
        remote_by_key[key] = (record["id"], row)

    create = [
        (
            _airtable_fields_for_schema(fields, table_schema, row["username"])
            if table_schema is not None
            else fields
        )
        for key, row in local_by_key.items()
        if key not in remote_by_key
        for fields in [_airtable_fields_from_managed_row(row)]
    ]
    update: list[dict[str, Any]] = []
    for key, row in local_by_key.items():
        remote = remote_by_key.get(key)
        if remote is None:
            continue
        record_id, remote_row = remote
        if any(row[name] != remote_row[name] for name in MANAGED_FIELDS):
            fields = _airtable_fields_from_managed_row(row)
            if table_schema is not None:
                fields = _airtable_fields_for_schema(fields, table_schema, row["username"])
            update.append({
                "record_id": record_id,
                "username": row["username"],
                "fields": fields,
            })
    delete = [
        {"record_id": record_id, "username": row["username"]}
        for key, (record_id, row) in remote_by_key.items()
        if key not in local_by_key
    ]
    return AirtableMirrorPlan(create=create, update=update, delete=delete)


def apply_airtable_mirror_plan(
    config: AirtableConfig,
    plan: AirtableMirrorPlan,
    requests_post: Callable[..., Any] = requests.post,
    requests_patch: Callable[..., Any] = requests.patch,
    requests_delete: Callable[..., Any] = requests.delete,
) -> dict[str, int]:
    """Aplica el espejo remoto en lotes de Airtable, incluyendo eliminaciones."""
    base_url = "https://api.airtable.com/v0/{}/{}".format(
        quote(config.base_id, safe=""), quote(config.table_name, safe="")
    )
    headers = {**_airtable_headers(config), "Content-Type": "application/json"}

    def request(method: str, response: Any, label: str) -> None:
        try:
            response.raise_for_status()
        except Exception as exc:
            raise AirtableSyncError(f"Airtable rechazó la sincronización ({method}: {label}).") from exc

    for start in range(0, len(plan.create), 10):
        batch = plan.create[start:start + 10]
        response = requests_post(
            base_url,
            headers=headers,
            json={"records": [{"fields": fields} for fields in batch]},
            timeout=20,
        )
        request("POST", response, "crear cuentas")

    for start in range(0, len(plan.update), 10):
        batch = plan.update[start:start + 10]
        response = requests_patch(
            base_url,
            headers=headers,
            json={"records": [{"id": item["record_id"], "fields": item["fields"]} for item in batch]},
            timeout=20,
        )
        request("PATCH", response, "actualizar cuentas")

    for item in plan.delete:
        record_url = f"{base_url}/{quote(item['record_id'], safe='')}"
        response = requests_delete(record_url, headers=_airtable_headers(config), timeout=20)
        request("DELETE", response, f"eliminar @{item['username']}")

    return {"created": len(plan.create), "updated": len(plan.update), "deleted": len(plan.delete)}


def build_account_sync_plan(
    remote_rows: list[AirtableAccount | dict[str, Any]],
    local_rows: list[dict[str, Any]],
) -> AccountSyncPlan:
    remote_by_key: dict[str, dict[str, Any]] = {}
    for raw_row in remote_rows:
        row = _coerce_managed_row(raw_row)
        key = row["username"].casefold()
        if key in remote_by_key:
            raise AirtableSyncError(f"Username duplicado en Airtable: @{row['username']}.")
        remote_by_key[key] = row

    local_by_key = {
        normalize_username(row.get("username")).casefold(): row
        for row in local_rows
        if normalize_username(row.get("username"))
    }
    create = [row for key, row in remote_by_key.items() if key not in local_by_key]
    update = []
    for key, row in remote_by_key.items():
        local = local_by_key.get(key)
        if local and any(
            local.get(name) != row[name]
            for name in MANAGED_FIELDS
            if name != "username"
        ):
            update.append(row)
    delete_usernames = [
        row["username"]
        for key, row in local_by_key.items()
        if key not in remote_by_key
    ]
    categories_to_add = sorted(
        {row["account_type"] for row in [*create, *update] if row["account_type"]},
        key=str.casefold,
    )
    return AccountSyncPlan(
        create=create,
        update=update,
        delete_usernames=sorted(delete_usernames, key=str.casefold),
        categories_to_add=categories_to_add,
    )
