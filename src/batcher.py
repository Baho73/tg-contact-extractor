# FILE: src/batcher.py
# VERSION: 1.0.0
# START_MODULE_CONTRACT
#   PURPOSE: Group messages into batches respecting count and token limits for LLM API calls
#   SCOPE: Token estimation, batch splitting
#   DEPENDS: M-PARSER (Message dataclass)
#   LINKS: M-BATCHER
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   estimate_tokens — rough token count for a message
#   make_batches — split messages into sized batches
# END_MODULE_MAP

from __future__ import annotations

import logging

from src.parser import Message

logger = logging.getLogger(__name__)


# START_CONTRACT: estimate_tokens
#   PURPOSE: Rough token count for a message (len/4 heuristic)
#   INPUTS: { message: Message }
#   OUTPUTS: { int — estimated token count }
#   SIDE_EFFECTS: none
#   LINKS: M-BATCHER
# END_CONTRACT: estimate_tokens
def estimate_tokens(message: Message) -> int:
    # ~4 chars per token is a common rough heuristic
    header = f"{message.from_user} [{message.date}]: "
    return (len(header) + len(message.text)) // 4 + 1


# START_CONTRACT: make_batches
#   PURPOSE: Split messages into batches by count and token limit
#   INPUTS: { messages: list[Message], batch_size: int, max_tokens: int }
#   OUTPUTS: { list[list[Message]] — batches }
#   SIDE_EFFECTS: none
#   LINKS: M-BATCHER
# END_CONTRACT: make_batches
def make_batches(
    messages: list[Message],
    batch_size: int = 50,
    max_tokens: int = 3000,
) -> list[list[Message]]:
    if not messages:
        logger.warning("[Batcher][make_batches] Empty input, returning empty list")
        return []

    # START_BLOCK_BUILD_BATCHES
    batches: list[list[Message]] = []
    current_batch: list[Message] = []
    current_tokens = 0

    for msg in messages:
        msg_tokens = estimate_tokens(msg)

        # If adding this message would exceed limits — flush current batch
        if current_batch and (
            len(current_batch) >= batch_size or current_tokens + msg_tokens > max_tokens
        ):
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(msg)
        current_tokens += msg_tokens

    # Don't forget the last batch
    if current_batch:
        batches.append(current_batch)
    # END_BLOCK_BUILD_BATCHES

    logger.info(
        "[Batcher][make_batches] Created %d batches from %d messages",
        len(batches), len(messages),
    )
    return batches


# START_CHANGE_SUMMARY
#   LAST_CHANGE: [v1.0.0 — Initial implementation: estimate_tokens, make_batches]
# END_CHANGE_SUMMARY
