# FILE: src/parser.py
# VERSION: 1.0.0
# START_MODULE_CONTRACT
#   PURPOSE: Parse Telegram Desktop JSON export into a list of normalized Message objects
#   SCOPE: File discovery, JSON parsing, rich-text flattening, filtering
#   DEPENDS: none
#   LINKS: M-PARSER
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Message — dataclass representing a single chat message
#   parse_export — main entry: path -> list[Message]
# END_MODULE_MAP

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# START_BLOCK_MESSAGE_DATACLASS
@dataclass
class Message:
    id: int
    date: str                # ISO 8601
    from_user: str           # sender display name
    from_id: str | None      # user_id if available
    text: str                # plain text (rich text flattened)
    reply_to_id: int | None
# END_BLOCK_MESSAGE_DATACLASS


# START_CONTRACT: _flatten_text
#   PURPOSE: Convert Telegram rich-text field (string or list of mixed items) to plain text
#   INPUTS: { raw: str | list — the "text" field from Telegram JSON }
#   OUTPUTS: { str — plain text }
#   SIDE_EFFECTS: none
#   LINKS: M-PARSER
# END_CONTRACT: _flatten_text
def _flatten_text(raw: str | list) -> str:
    if isinstance(raw, str):
        return raw

    # START_BLOCK_FLATTEN_RICH_TEXT
    parts: list[str] = []
    for item in raw:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            parts.append(item.get("text", ""))
    return "".join(parts)
    # END_BLOCK_FLATTEN_RICH_TEXT


# START_CONTRACT: _resolve_export_path
#   PURPOSE: Find result.json given a file or folder path
#   INPUTS: { path: Path — user-supplied path }
#   OUTPUTS: { Path — resolved path to result.json }
#   SIDE_EFFECTS: none
#   LINKS: M-PARSER
# END_CONTRACT: _resolve_export_path
def _resolve_export_path(path: Path) -> Path:
    if path.is_file():
        return path
    candidate = path / "result.json"
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"FILE_NOT_FOUND: result.json not found at {path}")


# START_CONTRACT: parse_export
#   PURPOSE: Main entry — parse Telegram Desktop JSON export into list[Message]
#   INPUTS: { path: Path — path to result.json or export folder }
#   OUTPUTS: { list[Message] — filtered and normalized messages }
#   SIDE_EFFECTS: none
#   LINKS: M-PARSER
# END_CONTRACT: parse_export
def parse_export(path: Path) -> list[Message]:
    resolved = _resolve_export_path(path)
    logger.info("[Parser][parse_export] Reading %s", resolved)

    # START_BLOCK_READ_JSON
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"INVALID_FORMAT: {exc}") from exc
    # END_BLOCK_READ_JSON

    if "messages" not in data:
        raise ValueError("INVALID_FORMAT: 'messages' key not found in JSON")

    # START_BLOCK_PARSE_MESSAGES
    messages: list[Message] = []
    for raw_msg in data["messages"]:
        # Skip non-message types (service messages, etc.)
        if raw_msg.get("type") != "message":
            continue

        text = _flatten_text(raw_msg.get("text", ""))

        # Skip empty messages (media-only)
        if not text.strip():
            continue

        msg = Message(
            id=raw_msg["id"],
            date=raw_msg.get("date", ""),
            from_user=raw_msg.get("from", raw_msg.get("from_id", "Unknown")),
            from_id=raw_msg.get("from_id"),
            text=text,
            reply_to_id=raw_msg.get("reply_to_message_id"),
        )
        messages.append(msg)
    # END_BLOCK_PARSE_MESSAGES

    logger.info("[Parser][parse_export] Parsed %d messages from %d total", len(messages), len(data["messages"]))
    return messages


# START_CHANGE_SUMMARY
#   LAST_CHANGE: [v1.0.0 — Initial implementation: Message dataclass, parse_export, rich-text flattening]
# END_CHANGE_SUMMARY
