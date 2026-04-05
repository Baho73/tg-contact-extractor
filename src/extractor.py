# FILE: src/extractor.py
# VERSION: 1.0.0
# START_MODULE_CONTRACT
#   PURPOSE: Send message batches to OpenRouter API and parse LLM responses into ContactRecord objects with dynamic contact types
#   SCOPE: API calls, retry logic, JSON response parsing, dataclasses
#   DEPENDS: M-CONFIG (AppConfig), M-PARSER (Message)
#   LINKS: M-EXTRACTOR
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   ContactField — dataclass: type (free-form str), value (str)
#   ContactRecord — dataclass: source_message_id, from_user, context, extracted[]
#   extract_contacts — process one batch -> list[ContactRecord]
#   process_all_batches — async generator yielding (batch_index, contacts) for progress
# END_MODULE_MAP

from __future__ import annotations

import asyncio
import json
import logging
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator

import httpx

from src.config import AppConfig
from src.parser import Message

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# START_BLOCK_PROMPT_MANAGEMENT
# START_CONTRACT: _prompts_dir
#   PURPOSE: Get prompts directory path for exe/dev mode
#   INPUTS: none
#   OUTPUTS: Path
# END_CONTRACT: _prompts_dir
def _prompts_dir() -> Path:
    """Directory for saved prompts — next to exe or project root."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "prompts"
    return Path(__file__).resolve().parent.parent / "prompts"


# START_CONTRACT: list_prompts
#   PURPOSE: List available prompt names from prompts/ folder
#   INPUTS: none
#   OUTPUTS: list[str]
# END_CONTRACT: list_prompts
def list_prompts() -> list[str]:
    """Return list of available prompt filenames (without extension)."""
    d = _prompts_dir()
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.txt"))


# START_CONTRACT: load_prompt
#   PURPOSE: Load prompt text by name
#   INPUTS: { name: str }
#   OUTPUTS: str
#   SIDE_EFFECTS: none
# END_CONTRACT: load_prompt
def load_prompt(name: str) -> str:
    """Load prompt text by name (filename without .txt)."""
    path = _prompts_dir() / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip()


# START_CONTRACT: save_prompt
#   PURPOSE: Save prompt text to file
#   INPUTS: { name: str, text: str }
#   OUTPUTS: Path
#   SIDE_EFFECTS: writes to prompts/name.txt
# END_CONTRACT: save_prompt
def save_prompt(name: str, text: str) -> Path:
    """Save prompt text to file. Returns path."""
    d = _prompts_dir()
    d.mkdir(exist_ok=True)
    path = d / f"{name}.txt"
    path.write_text(text, encoding="utf-8")
    return path


DEFAULT_PROMPT_NAME = "vacancies"
# END_BLOCK_PROMPT_MANAGEMENT


# START_BLOCK_DATACLASSES
@dataclass
class ContactField:
    type: str   # free-form: "телефон", "ИНН", "email", etc.
    value: str


@dataclass
class ContactRecord:
    source_message_id: int
    from_user: str
    context: str
    extracted: list[ContactField] = field(default_factory=list)
# END_BLOCK_DATACLASSES


# START_CONTRACT: _format_batch_for_prompt
#   PURPOSE: Format a batch of messages into a text prompt for the LLM
#   INPUTS: { batch: list[Message] }
#   OUTPUTS: { str }
#   SIDE_EFFECTS: none
# END_CONTRACT: _format_batch_for_prompt
def _format_batch_for_prompt(batch: list[Message]) -> str:
    lines: list[str] = []
    for msg in batch:
        lines.append(f"[ID:{msg.id}] {msg.from_user} ({msg.date}): {msg.text}")
    return "\n".join(lines)


# START_CONTRACT: _parse_llm_response
#   PURPOSE: Parse LLM JSON response into ContactRecord list (supports both {"contacts":[...]} and bare [...] formats)
#   INPUTS: { raw_text: str }
#   OUTPUTS: { list[ContactRecord] }
#   SIDE_EFFECTS: none
#   NOTE: Raises json.JSONDecodeError on invalid JSON
# END_CONTRACT: _parse_llm_response
def _parse_llm_response(raw_text: str) -> list[ContactRecord]:
    # START_BLOCK_PARSE_RESPONSE
    data = json.loads(raw_text)

    # Handle string, list, or dict responses
    if isinstance(data, str):
        return []
    contacts_raw = data if isinstance(data, list) else data.get("contacts", [])

    records: list[ContactRecord] = []
    for item in contacts_raw:
        fields = [
            ContactField(type=f["type"], value=f["value"])
            for f in item.get("extracted", [])
        ]
        records.append(ContactRecord(
            source_message_id=item.get("source_message_id", 0),
            from_user=item.get("from_user", ""),
            context=item.get("context", ""),
            extracted=fields,
        ))
    return records
    # END_BLOCK_PARSE_RESPONSE


# START_CONTRACT: extract_contacts
#   PURPOSE: Process one batch — send to OpenRouter API, parse response
#   INPUTS: { batch: list[Message], config: AppConfig, client: httpx.AsyncClient, system_prompt: str | None }
#   OUTPUTS: { list[ContactRecord] — extracted contacts }
#   SIDE_EFFECTS: HTTP request to OpenRouter API
#   LINKS: M-EXTRACTOR, M-CONFIG
# END_CONTRACT: extract_contacts
async def extract_contacts(
    batch: list[Message],
    config: AppConfig,
    client: httpx.AsyncClient,
    system_prompt: str | None = None,
) -> list[ContactRecord]:
    user_content = _format_batch_for_prompt(batch)
    prompt = system_prompt or load_prompt(DEFAULT_PROMPT_NAME)

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {config.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    # START_BLOCK_RETRY_LOGIC
    max_retries = config.max_retries
    base_timeout = config.base_timeout

    for attempt in range(max_retries):
        try:
            timeout = base_timeout * (2 ** attempt)
            resp = await client.post(
                OPENROUTER_URL,
                json=payload,
                headers=headers,
                timeout=timeout,
            )

            if resp.status_code == 429:
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "[Extractor][extract_contacts][RETRY_LOGIC] Rate limited (429), waiting %.1fs",
                    wait,
                )
                await asyncio.sleep(wait)
                continue

            resp.raise_for_status()
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            return _parse_llm_response(content)

        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
            logger.warning(
                "[Extractor][extract_contacts][RETRY_LOGIC] Invalid response (attempt %d/%d): %s",
                attempt + 1, max_retries, exc,
            )
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)

        except httpx.TimeoutException:
            logger.warning(
                "[Extractor][extract_contacts][RETRY_LOGIC] Timeout (attempt %d/%d), increasing timeout",
                attempt + 1, max_retries,
            )
            if attempt == max_retries - 1:
                raise

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 500, 502, 503, 504):
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "[Extractor][extract_contacts][RETRY_LOGIC] HTTP %d, waiting %.1fs",
                    exc.response.status_code, wait,
                )
                await asyncio.sleep(wait)
                continue
            raise
    # END_BLOCK_RETRY_LOGIC

    return []


# START_CONTRACT: process_all_batches
#   PURPOSE: Async generator — yields (batch_index, list[ContactRecord]) for progress tracking
#   INPUTS: { batches: list[list[Message]], config: AppConfig, system_prompt: str | None }
#   OUTPUTS: { AsyncGenerator yielding (int, list[ContactRecord]) }
#   SIDE_EFFECTS: HTTP requests to OpenRouter API
#   LINKS: M-EXTRACTOR
# END_CONTRACT: process_all_batches
async def process_all_batches(
    batches: list[list[Message]],
    config: AppConfig,
    system_prompt: str | None = None,
) -> AsyncGenerator[tuple[int, list[ContactRecord], list[int] | None], None]:
    async with httpx.AsyncClient() as client:
        for i, batch in enumerate(batches):
            try:
                contacts = await extract_contacts(batch, config, client, system_prompt)
                yield (i, contacts, None)
            except Exception as exc:
                msg_ids = [m.id for m in batch]
                logger.error(
                    "[Extractor][process_all_batches] Batch %d failed (messages %d-%d): %s",
                    i, msg_ids[0], msg_ids[-1], exc,
                )
                yield (i, [], msg_ids)


# START_CHANGE_SUMMARY
#   LAST_CHANGE: [v1.0.0 — Initial implementation: ContactField, ContactRecord, extract_contacts with retry, process_all_batches]
# END_CHANGE_SUMMARY
