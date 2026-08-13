"""Lectura y conciliación unidireccional de cuentas desde Airtable."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import json
from urllib.parse import quote

import requests


CONFIG_FILE = Path(__file__).with_name("airtable_config.json")
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
    AirtableRequiredField("Categoría", "singleLineText"),
    AirtableRequiredField("Trials desbloqueados", "checkbox"),
    AirtableRequiredField("Día", "singleLineText"),
    AirtableRequiredField("Red social", "singleLineText"),
    AirtableRequiredField("VPN / Proxy", "multilineText"),
    AirtableRequiredField("Link", "url"),
)


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
    raise AirtableSyncError(f"'{name}' debe ser un checkbox.")


def _account_from_record(record: dict[str, Any]) -> AirtableAccount:
    fields = record.get("fields") or {}
    if not isinstance(fields, dict):
        raise AirtableSyncError("Airtable devolvió una fila inválida.")
    username = normalize_username(fields.get("Username"))
    account_type = _text(fields, "Categoría")
    if not username:
        raise AirtableSyncError("Cada fila debe tener Username.")
    if not account_type:
        raise AirtableSyncError(f"La cuenta @{username} no tiene Categoría.")
    return AirtableAccount(
        username=username,
        two_factor=_text(fields, "2FA"),
        assigned_va=_text(fields, "VA", "Sin Asignar") or "Sin Asignar",
        account_type=account_type,
        trials_active=_checkbox(fields, "Trials desbloqueados"),
        account_day=_text(fields, "Día"),
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


def _airtable_error_code(response: Any) -> str:
    """Devuelve solo el tipo de error público de Airtable, nunca el cuerpo ni token."""
    try:
        payload = response.json()
        code = payload.get("error", {}).get("type", "") if isinstance(payload, dict) else ""
    except Exception:
        return ""
    return code if isinstance(code, str) and code.replace("_", "").isalnum() else ""


def prepare_airtable_account_table(
    config: AirtableConfig,
    requests_get: Callable[..., Any] = requests.get,
    requests_post: Callable[..., Any] = requests.post,
) -> AirtableSchemaPreparation:
    """Agrega solamente los campos requeridos que aún no existen en la tabla."""
    table = _configured_table_schema(config, requests_get)
    existing_types = {
        field.get("name"): field.get("type")
        for field in table["fields"]
        if isinstance(field, dict) and isinstance(field.get("name"), str)
    }
    fields_url = "https://api.airtable.com/v0/meta/bases/{}/tables/{}/fields".format(
        quote(config.base_id, safe=""), quote(table["id"], safe="")
    )
    added: list[str] = []
    incompatible: list[tuple[str, str, str]] = []
    for required in AIRTABLE_ACCOUNT_COLUMNS:
        existing_type = existing_types.get(required.name)
        if existing_type is not None:
            if existing_type != required.field_type:
                incompatible.append((required.name, str(existing_type), required.field_type))
            continue
        response = None
        try:
            response = requests_post(
                fields_url,
                headers=_airtable_headers(config),
                json={"name": required.name, "type": required.field_type},
                timeout=20,
            )
            response.raise_for_status()
        except Exception as exc:
            status_code = getattr(response, "status_code", None)
            diagnostic = f"HTTP {status_code}" if isinstance(status_code, int) else "HTTP desconocido"
            error_code = _airtable_error_code(response) if response is not None else ""
            if error_code:
                diagnostic = f"{diagnostic}: {error_code}"
            if status_code == 401:
                message = f"El token de Airtable es inválido o fue revocado ({diagnostic})."
            elif status_code in (403, 404):
                message = (
                    "El token fue aceptado, pero no tiene permiso para editar la estructura de esta base. "
                    "Confirma acceso a esta base y schema.bases:write. "
                    f"Airtable rechazó '{required.name}' ({diagnostic})."
                )
            else:
                message = (
                    "No se pudo crear una columna en Airtable. "
                    f"Airtable rechazó '{required.name}' ({diagnostic})."
                )
            raise AirtableSyncError(
                message
            ) from exc
        added.append(required.name)
    return AirtableSchemaPreparation(tuple(added), tuple(incompatible))


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
            account = _account_from_record(record)
            key = account.username.casefold()
            if key in seen:
                raise AirtableSyncError(f"Username duplicado en Airtable: @{account.username}.")
            seen.add(key)
            accounts.append(account)
        offset = payload.get("offset")
        if not offset:
            return accounts


def _coerce_managed_row(row: AirtableAccount | dict[str, Any]) -> dict[str, Any]:
    values = row.as_managed_dict() if isinstance(row, AirtableAccount) else dict(row)
    username = normalize_username(values.get("username"))
    account_type = str(values.get("account_type") or "").strip()
    if not username or not account_type:
        raise AirtableSyncError("Cada cuenta necesita Username y Categoría.")
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
