"""Read models and deterministic eligibility policy for operational content CRM."""
from __future__ import annotations


ACTIVE_USE_STATES = ("assigned", "scheduled", "sent_telegram", "published_confirmed")
SUCCESSFUL_HISTORY_STATES = ("sent_telegram", "published_confirmed")


def list_root_cards(db, search="", account_id=None, include_archived=False):
    cards = []
    for summary in db.list_root_operational_summary(search, include_archived):
        if account_id is not None:
            uses = db.list_content_account_uses(account_id=int(account_id), root_id=summary["id"])
            if not uses:
                continue
        cards.append(
            {
                "id": summary["id"],
                "name": summary["name"],
                "status": summary["status"],
                "asset_count": summary["asset_count"],
                "usable_output_count": len(db.list_root_usable_outputs(summary["id"])),
                "scheduled_count": summary["scheduled_count"],
                "sent_telegram_count": summary["sent_telegram_count"],
                "successful_use_count": summary["successful_use_count"],
                "last_successful_use_at": summary["last_successful_use_at"],
            }
        )
    return cards


def list_account_content(db, account_id):
    content = []
    roots = {}
    for use in db.list_content_account_uses(account_id=int(account_id)):
        root_id = use.get("content_root_id")
        if root_id is not None and root_id not in roots:
            roots[root_id] = db.get_content_root(root_id)
        root = roots.get(root_id)
        content.append({**use, "root_name": root["name"] if root else None})
    return content


def evaluate_reuse(db, root_id, account_ids, delivery_kind="normal"):
    root = db.get_content_root(root_id)
    if not root or root["status"] != "active":
        raise ValueError("La familia seleccionada no esta disponible.")

    accounts = {account["id"]: account for account in db.list_accounts_by_ids(account_ids)}
    ordered_accounts = [accounts[account_id] for account_id in map(int, account_ids) if account_id in accounts]
    usable_outputs = db.list_root_usable_outputs(root["id"])
    active_root_uses = _uses_by_account(db.list_active_uses_for_root(root["id"]))
    active_asset_uses = _uses_by_account(
        db.list_active_uses_for_assets([asset["id"] for asset in usable_outputs])
    )

    eligible = []
    excluded = []
    for account in ordered_accounts:
        reason = _reuse_exclusion_reason(
            account,
            delivery_kind,
            active_root_uses.get(account["id"], []),
            active_asset_uses.get(account["id"], []),
            bool(usable_outputs),
        )
        record = {"account_id": account["id"], "username": account["username"]}
        if reason:
            excluded.append({**record, "reason": reason})
        else:
            eligible.append(record)
    return {"eligible": eligible, "excluded": excluded}


def build_reuse_request(db, root_id, account_ids, delivery_kind="normal"):
    """Build the explicit handoff that Logistics may schedule for a content root."""
    decision = evaluate_reuse(db, root_id, account_ids, delivery_kind)
    if not decision["eligible"]:
        raise ValueError("No hay cuentas elegibles para reutilizar esta familia.")
    return {
        "root_id": int(root_id),
        "delivery_kind": str(delivery_kind),
        "eligible_account_ids": [item["account_id"] for item in decision["eligible"]],
        "asset_ids": [asset["id"] for asset in db.list_root_usable_outputs(root_id)],
        "decision": decision,
    }


def _uses_by_account(uses):
    grouped = {}
    for use in uses:
        grouped.setdefault(use.get("account_id"), []).append(use)
    return grouped


def _reuse_exclusion_reason(account, delivery_kind, root_uses, asset_uses, has_usable_output):
    if not _supports_delivery_kind(account, delivery_kind):
        return "wrong_delivery_kind"
    if root_uses:
        if any(use["state"] in SUCCESSFUL_HISTORY_STATES for use in root_uses):
            return "already_sent_root"
        return "already_scheduled_root"
    if asset_uses:
        return "same_asset_scheduled"
    if not has_usable_output:
        return "missing_usable_output"
    return None


def _supports_delivery_kind(account, delivery_kind):
    if delivery_kind == "normal":
        return True
    if delivery_kind == "trial":
        return bool(account.get("trials_active"))
    return False
