"""Pure preview contract for the shared logistics planner.

This module deliberately has no filesystem, SQLite, Telegram, or GUI side effects.
"""
from __future__ import annotations

import math
import random


def assess_candidate_eligibility(
    candidate: dict,
    *,
    username: str,
    lane: str,
    allow_reuse: bool = False,
) -> dict:
    """Evaluate one candidate for one account and publication lane."""
    account = _required_label(username, "username").casefold()
    lane_label = _required_label(lane, "lane")
    delivery_kind = str(candidate.get("delivery_kind") or "").strip().lower()
    if (delivery_kind == "trial" and lane_label != "trial_reel") or (
        delivery_kind == "normal" and lane_label == "trial_reel"
    ):
        return {
            "eligible": False,
            "reason": "trial_lane_mismatch",
            "context_usage_count": 0,
        }

    same_lane = 0
    context_usage_count = 0
    for usage in candidate.get("used_in") or []:
        if not isinstance(usage, dict):
            continue
        if str(usage.get("username") or "").strip().casefold() != account:
            continue
        if str(usage.get("lane") or "").strip() == lane_label:
            same_lane += 1
        else:
            context_usage_count += 1
    if same_lane and not allow_reuse:
        return {
            "eligible": False,
            "reason": "already_used_in_lane",
            "context_usage_count": context_usage_count,
        }
    return {"eligible": True, "reason": "", "context_usage_count": context_usage_count}


def filter_candidates_for_account(
    candidates: list[dict],
    *,
    username: str,
    lane: str,
    allow_reuse: bool = False,
) -> dict:
    """Return eligible candidates plus auditable exclusions for one account."""
    account = _required_label(username, "username")
    lane_label = _required_label(lane, "lane")
    eligible = []
    excluded = []
    for candidate in candidates:
        source_id = _required_label(
            candidate.get("source_id") or candidate.get("source_path"), "source_id"
        )
        assessment = assess_candidate_eligibility(
            candidate,
            username=account,
            lane=lane_label,
            allow_reuse=allow_reuse,
        )
        if assessment["eligible"]:
            eligible.append(candidate)
            continue
        excluded.append(
            {
                "source_id": source_id,
                "username": account,
                "lane": lane_label,
                "reason": assessment["reason"],
            }
        )
    return {"candidates": eligible, "excluded": excluded}


def preview_shared_schedule(
    *,
    accounts: list[dict],
    candidates: list[dict],
    daily_quota: int,
    days: int | str,
    lane: str = "reel",
    placement: str = "feed",
    method: str = "telegram",
    mode: str = "partial",
    seed: int | None = None,
) -> dict:
    """Build a deterministic schedule preview without consuming any input.

    Candidates are concrete content records and must have a unique ``source_id``.
    ``MAX`` uses the smallest number of days needed to expose every candidate.
    """
    normalized_accounts = _normalize_accounts(accounts)
    normalized_candidates = _normalize_candidates(candidates)
    quota = _positive_int(daily_quota, "daily_quota")
    mode_label = str(mode or "").strip().lower()
    if mode_label not in {"partial", "strict"}:
        raise ValueError("mode debe ser partial o strict")
    lane_label = _required_label(lane, "lane")
    placement_label = _required_label(placement, "placement")
    method_label = _required_label(method, "method")
    random_seed = 0 if seed is None else int(seed)

    if isinstance(days, str) and days.strip().upper() == "MAX":
        target_days = (
            math.ceil(len(normalized_candidates) / (len(normalized_accounts) * quota))
            if normalized_candidates
            else 0
        )
    else:
        target_days = _positive_int(days, "days")

    requested = target_days * len(normalized_accounts) * quota
    shuffled = list(normalized_candidates)
    random.Random(random_seed).shuffle(shuffled)
    assignments = []
    omitted = []
    candidate_index = 0
    for day in range(1, target_days + 1):
        for slot in range(1, quota + 1):
            for account in normalized_accounts:
                if candidate_index < len(shuffled):
                    assignment = dict(shuffled[candidate_index])
                    assignment.update(
                        {
                            "username": account["username"],
                            "account_id": account.get("account_id"),
                            "day": day,
                            "slot": slot,
                            "lane": lane_label,
                            "placement": placement_label,
                            "method": method_label,
                        }
                    )
                    assignments.append(assignment)
                    candidate_index += 1
                else:
                    omitted.append(
                        {
                            "username": account["username"],
                            "day": day,
                            "slot": slot,
                            "lane": lane_label,
                            "placement": placement_label,
                            "reason": "insufficient_inventory",
                        }
                    )

    assignable = len(assignments)
    omitted_count = len(omitted)
    status = "ready"
    if omitted_count:
        status = "blocked" if mode_label == "strict" else "partial"
        if mode_label == "strict":
            assignments = []

    return {
        "plan_version": 1,
        "status": status,
        "mode": mode_label,
        "seed": random_seed,
        "scope": {
            "lane": lane_label,
            "placement": placement_label,
            "method": method_label,
        },
        "summary": {
            "requested": requested,
            "assignable": assignable,
            "omitted": omitted_count,
            "accounts": len(normalized_accounts),
            "days": target_days,
            "daily_quota": quota,
        },
        "assignments": assignments,
        "omitted": omitted,
    }


def _normalize_accounts(accounts: list[dict]) -> list[dict]:
    if not accounts:
        raise ValueError("accounts no puede estar vacio")
    normalized = []
    seen = set()
    for account in accounts:
        if not isinstance(account, dict):
            raise ValueError("cada account debe ser un objeto")
        username = _required_label(account.get("username"), "username")
        key = username.casefold()
        if key in seen:
            raise ValueError("username duplicado en accounts")
        seen.add(key)
        normalized.append({**account, "username": username})
    return normalized


def _normalize_candidates(candidates: list[dict]) -> list[dict]:
    normalized = []
    seen = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("cada candidate debe ser un objeto")
        source_id = _required_label(
            candidate.get("source_id") or candidate.get("source_path"), "source_id"
        )
        if source_id in seen:
            raise ValueError("source_id duplicado en candidates")
        seen.add(source_id)
        normalized.append({**candidate, "source_id": source_id})
    return normalized


def _positive_int(value, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} debe ser un entero positivo") from exc
    if number < 1:
        raise ValueError(f"{field} debe ser un entero positivo")
    return number


def _required_label(value, field: str) -> str:
    label = str(value or "").strip()
    if not label:
        raise ValueError(f"{field} no puede estar vacio")
    return label
