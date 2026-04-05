# FILE: src/writer.py
# VERSION: 1.0.0
# START_MODULE_CONTRACT
#   PURPOSE: Serialize extracted contacts to a JSON file with metadata, supporting incremental writes
#   SCOPE: JSON serialization, incremental flush, metadata
#   DEPENDS: M-EXTRACTOR (ContactRecord, ContactField)
#   LINKS: M-WRITER
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   ExtractionMeta — dataclass for output metadata
#   write_json — write final JSON with all contacts and metadata
#   flush_incremental — append batch results to temp file for crash recovery
# END_MODULE_MAP

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path

from src.extractor import ContactRecord

logger = logging.getLogger(__name__)


# START_BLOCK_EXTRACTION_META
@dataclass
class ExtractionMeta:
    source: str
    total_messages: int
    processed_batches: int
    skipped_batches: list[list[int]] = field(default_factory=list)  # list of msg ID ranges
    date: str = ""
    prompt: str = ""  # system prompt used for extraction
# END_BLOCK_EXTRACTION_META


# START_CONTRACT: _contact_to_dict
#   PURPOSE: Convert ContactRecord to JSON-serializable dict
#   INPUTS: { record: ContactRecord }
#   OUTPUTS: dict
# END_CONTRACT: _contact_to_dict
def _contact_to_dict(record: ContactRecord) -> dict:
    return {
        "source_message_id": record.source_message_id,
        "from_user": record.from_user,
        "context": record.context,
        "extracted": [
            {"type": f.type, "value": f.value}
            for f in record.extracted
        ],
    }


# START_CONTRACT: flush_incremental
#   PURPOSE: Append batch results to a temp JSONL file for crash recovery
#   INPUTS: { contacts: list[ContactRecord], temp_path: Path }
#   OUTPUTS: None
#   SIDE_EFFECTS: Appends lines to temp file
#   LINKS: M-WRITER
# END_CONTRACT: flush_incremental
def flush_incremental(contacts: list[ContactRecord], temp_path: Path) -> None:
    # START_BLOCK_INCREMENTAL_WRITE
    with open(temp_path, "a", encoding="utf-8") as f:
        for record in contacts:
            f.write(json.dumps(_contact_to_dict(record), ensure_ascii=False) + "\n")
    logger.info("[Writer][flush_incremental] Flushed %d contacts to %s", len(contacts), temp_path)
    # END_BLOCK_INCREMENTAL_WRITE


# START_CONTRACT: write_json
#   PURPOSE: Write final JSON with all contacts and metadata
#   INPUTS: { contacts: list[ContactRecord], meta: ExtractionMeta, output_path: Path }
#   OUTPUTS: { Path — path to written JSON file }
#   SIDE_EFFECTS: Writes JSON file to disk
#   LINKS: M-WRITER
# END_CONTRACT: write_json
def write_json(
    contacts: list[ContactRecord],
    meta: ExtractionMeta,
    output_path: Path,
) -> Path:
    # START_BLOCK_BUILD_OUTPUT
    output = {
        "extraction_meta": {
            "source": meta.source,
            "total_messages": meta.total_messages,
            "processed_batches": meta.processed_batches,
            "skipped_batches": meta.skipped_batches,
            "date": meta.date,
            "prompt": meta.prompt,
        },
        "contacts": [_contact_to_dict(c) for c in contacts],
    }
    # END_BLOCK_BUILD_OUTPUT

    # START_BLOCK_WRITE_FILE
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(
        "[Writer][write_json] Wrote %d contacts to %s", len(contacts), output_path,
    )
    # END_BLOCK_WRITE_FILE

    return output_path


# START_CHANGE_SUMMARY
#   LAST_CHANGE: [v1.0.0 — Initial implementation: ExtractionMeta, write_json, flush_incremental]
# END_CHANGE_SUMMARY
