from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from calendar_manifest import apply_manifest_preview, preview_migrate_manifest_v1_to_v2


def _json_dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _preview(manifest_path: Path) -> int:
    preview = preview_migrate_manifest_v1_to_v2(manifest_path)
    print(_json_dump(preview))
    return 0


def _apply(manifest_path: Path, *, require_confirmation: bool, yes: bool) -> int:
    if require_confirmation and not yes:
        print("La migracion requiere --yes para aplicar cambios.", file=sys.stderr)
        return 2
    preview = preview_migrate_manifest_v1_to_v2(manifest_path)
    applied = apply_manifest_preview(manifest_path, preview)
    print(
        _json_dump(
            {
                "applied": True,
                "manifest_path": str(manifest_path),
                "entries": len(applied),
                "summary": preview["summary"],
            }
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview/apply calendar_manifest v1 to v2 migration."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview = subparsers.add_parser("preview", help="Print migration preview JSON.")
    preview.add_argument("manifest_path", type=Path)

    apply = subparsers.add_parser("apply", help="Apply migration after preview.")
    apply.add_argument("manifest_path", type=Path)
    apply.add_argument(
        "--require-confirmation",
        action="store_true",
        help="Require --yes before writing.",
    )
    apply.add_argument("--yes", action="store_true", help="Confirm write operation.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "preview":
            return _preview(args.manifest_path)
        if args.command == "apply":
            return _apply(
                args.manifest_path,
                require_confirmation=args.require_confirmation,
                yes=args.yes,
            )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.error(f"comando no soportado: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
