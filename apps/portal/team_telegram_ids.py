"""Parse team broadcast chat IDs from portal textarea (comma / newline / semicolon)."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"^-?\d{1,32}$")


def parse_team_telegram_chat_ids_input(text: str) -> tuple[list[str], list[str]]:
    """Return (valid_ids, invalid_tokens). Valid IDs are decimal strings, optional leading minus."""
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    tokens: list[str] = []
    for line in raw.split("\n"):
        for part in line.split(","):
            for piece in part.split(";"):
                t = piece.strip()
                if t:
                    tokens.append(t)
    valid: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        if not _TOKEN_RE.fullmatch(t):
            invalid.append(t)
            continue
        if t not in seen:
            seen.add(t)
            valid.append(t)
    return valid, invalid
