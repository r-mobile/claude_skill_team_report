#!/usr/bin/env python3
"""Manage the employee email roster used for the weekly team report.

The roster is stored as a JSON array of lowercase email strings in
emails.json, located in the skill root (one level up from this script).

Usage:
    python manage_emails.py list
    python manage_emails.py add user@example.com [user2@example.com ...]
    python manage_emails.py remove user@example.com [user2@example.com ...]
    python manage_emails.py clear

Commands print the resulting roster as JSON to stdout and exit non-zero on
invalid input so the caller can detect failures.
"""
import json
import re
import sys
from pathlib import Path

STORE = Path(__file__).resolve().parent.parent / "emails.json"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def load() -> list[str]:
    if not STORE.exists():
        return []
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(e).strip().lower() for e in data if str(e).strip()]


def save(emails: list[str]) -> None:
    # de-duplicate while preserving order
    seen: dict[str, None] = {}
    for e in emails:
        seen.setdefault(e.strip().lower(), None)
    STORE.write_text(
        json.dumps(list(seen), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def valid(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip().lower()))


def main(argv: list[str]) -> int:
    if not argv:
        print("error: missing command (list|add|remove|clear)", file=sys.stderr)
        return 2

    cmd, args = argv[0].lower(), argv[1:]
    emails = load()

    if cmd == "list":
        pass
    elif cmd == "clear":
        emails = []
        save(emails)
    elif cmd == "add":
        if not args:
            print("error: 'add' needs at least one email", file=sys.stderr)
            return 2
        invalid = [a for a in args if not valid(a)]
        if invalid:
            print(f"error: invalid email(s): {', '.join(invalid)}", file=sys.stderr)
            return 2
        emails.extend(a.strip().lower() for a in args)
        save(emails)
        emails = load()
    elif cmd == "remove":
        if not args:
            print("error: 'remove' needs at least one email", file=sys.stderr)
            return 2
        drop = {a.strip().lower() for a in args}
        emails = [e for e in emails if e not in drop]
        save(emails)
    else:
        print(f"error: unknown command '{cmd}'", file=sys.stderr)
        return 2

    print(json.dumps({"count": len(emails), "emails": emails}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
