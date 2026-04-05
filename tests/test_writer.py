import json
from pathlib import Path

from src.extractor import ContactField, ContactRecord
from src.writer import ExtractionMeta, flush_incremental, write_json


def _sample_contacts() -> list[ContactRecord]:
    return [
        ContactRecord(
            source_message_id=1,
            from_user="Alice",
            context="shared phone",
            extracted=[
                ContactField(type="телефон", value="+7 999 000 00 00"),
                ContactField(type="ФИО", value="Иванов Пётр"),
            ],
        ),
        ContactRecord(
            source_message_id=5,
            from_user="Bob",
            context="company info",
            extracted=[
                ContactField(type="email", value="info@test.ru"),
                ContactField(type="ИНН", value="7712345678"),
            ],
        ),
    ]


def _sample_meta() -> ExtractionMeta:
    return ExtractionMeta(
        source="test/result.json",
        total_messages=100,
        processed_batches=2,
        skipped_batches=[],
        date="2026-04-05",
    )


def test_write_json_creates_file(tmp_path: Path):
    output = tmp_path / "output.json"
    result = write_json(_sample_contacts(), _sample_meta(), output)

    assert result == output
    assert output.exists()

    data = json.loads(output.read_text(encoding="utf-8"))
    assert "extraction_meta" in data
    assert "contacts" in data
    assert len(data["contacts"]) == 2


def test_write_json_structure(tmp_path: Path):
    output = tmp_path / "output.json"
    write_json(_sample_contacts(), _sample_meta(), output)
    data = json.loads(output.read_text(encoding="utf-8"))

    meta = data["extraction_meta"]
    assert meta["source"] == "test/result.json"
    assert meta["total_messages"] == 100
    assert meta["date"] == "2026-04-05"

    contact = data["contacts"][0]
    assert contact["source_message_id"] == 1
    assert contact["from_user"] == "Alice"
    assert len(contact["extracted"]) == 2
    assert contact["extracted"][0]["type"] == "телефон"
    assert contact["extracted"][0]["value"] == "+7 999 000 00 00"


def test_write_json_empty_contacts(tmp_path: Path):
    output = tmp_path / "output.json"
    write_json([], _sample_meta(), output)
    data = json.loads(output.read_text(encoding="utf-8"))

    assert data["contacts"] == []


def test_write_json_skipped_batches(tmp_path: Path):
    output = tmp_path / "output.json"
    meta = ExtractionMeta(
        source="test.json",
        total_messages=500,
        processed_batches=10,
        skipped_batches=[[101, 102, 103], [250, 251]],
        date="2026-04-05",
    )
    write_json([], meta, output)
    data = json.loads(output.read_text(encoding="utf-8"))

    assert len(data["extraction_meta"]["skipped_batches"]) == 2


def test_flush_incremental(tmp_path: Path):
    temp = tmp_path / "temp.jsonl"
    contacts = _sample_contacts()

    flush_incremental(contacts[:1], temp)
    flush_incremental(contacts[1:], temp)

    lines = temp.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["source_message_id"] == 1

    second = json.loads(lines[1])
    assert second["source_message_id"] == 5


def test_write_json_unicode(tmp_path: Path):
    output = tmp_path / "output.json"
    contacts = [
        ContactRecord(
            source_message_id=1,
            from_user="Катя",
            context="контакт Петра Ивановича",
            extracted=[ContactField(type="ФИО", value="Пётр Иванович Сидоров")],
        ),
    ]
    write_json(contacts, _sample_meta(), output)

    raw = output.read_text(encoding="utf-8")
    assert "Пётр Иванович Сидоров" in raw  # ensure_ascii=False
    assert "\\u" not in raw  # no escaped unicode
