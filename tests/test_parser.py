import json
from pathlib import Path

from src.parser import Message, parse_export, _flatten_text


def _make_export(messages: list[dict], tmp_path: Path) -> Path:
    data = {"name": "Test Chat", "type": "personal_chat", "messages": messages}
    path = tmp_path / "result.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_parse_simple_messages(tmp_path: Path):
    raw_messages = [
        {
            "id": 1,
            "type": "message",
            "date": "2026-01-15T10:30:00",
            "from": "Alice",
            "from_id": "user123",
            "text": "Привет, мой телефон +7 999 123 45 67",
        },
        {
            "id": 2,
            "type": "message",
            "date": "2026-01-15T10:31:00",
            "from": "Bob",
            "from_id": "user456",
            "text": "Ок, записал",
        },
    ]
    path = _make_export(raw_messages, tmp_path)
    messages = parse_export(path)

    assert len(messages) == 2
    assert messages[0].id == 1
    assert messages[0].from_user == "Alice"
    assert "+7 999 123 45 67" in messages[0].text
    assert messages[1].from_user == "Bob"


def test_skip_service_messages(tmp_path: Path):
    raw_messages = [
        {"id": 1, "type": "service", "date": "2026-01-15T10:00:00", "text": "joined"},
        {"id": 2, "type": "message", "date": "2026-01-15T10:01:00", "from": "A", "text": "hello"},
    ]
    path = _make_export(raw_messages, tmp_path)
    messages = parse_export(path)

    assert len(messages) == 1
    assert messages[0].id == 2


def test_skip_empty_messages(tmp_path: Path):
    raw_messages = [
        {"id": 1, "type": "message", "date": "2026-01-15T10:00:00", "from": "A", "text": ""},
        {"id": 2, "type": "message", "date": "2026-01-15T10:00:00", "from": "A", "text": "  "},
        {"id": 3, "type": "message", "date": "2026-01-15T10:01:00", "from": "A", "text": "ok"},
    ]
    path = _make_export(raw_messages, tmp_path)
    messages = parse_export(path)

    assert len(messages) == 1
    assert messages[0].id == 3


def test_flatten_rich_text():
    rich = [
        "Звони ",
        {"type": "phone", "text": "+7 999 000 00 00"},
        " — это Петр",
    ]
    assert _flatten_text(rich) == "Звони +7 999 000 00 00 — это Петр"


def test_flatten_plain_string():
    assert _flatten_text("просто строка") == "просто строка"


def test_rich_text_in_export(tmp_path: Path):
    raw_messages = [
        {
            "id": 1,
            "type": "message",
            "date": "2026-01-15T10:00:00",
            "from": "A",
            "text": ["Текст ", {"type": "bold", "text": "жирный"}, " конец"],
        },
    ]
    path = _make_export(raw_messages, tmp_path)
    messages = parse_export(path)

    assert len(messages) == 1
    assert messages[0].text == "Текст жирный конец"


def test_folder_path_resolution(tmp_path: Path):
    _make_export(
        [{"id": 1, "type": "message", "date": "2026-01-15", "from": "A", "text": "hi"}],
        tmp_path,
    )
    messages = parse_export(tmp_path)  # pass folder, not file
    assert len(messages) == 1


def test_file_not_found(tmp_path: Path):
    try:
        parse_export(tmp_path / "nonexistent.json")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


def test_invalid_json(tmp_path: Path):
    path = tmp_path / "result.json"
    path.write_text("not json", encoding="utf-8")
    try:
        parse_export(path)
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "INVALID_FORMAT" in str(exc)


def test_reply_to_id(tmp_path: Path):
    raw_messages = [
        {
            "id": 1, "type": "message", "date": "2026-01-15",
            "from": "A", "text": "question",
        },
        {
            "id": 2, "type": "message", "date": "2026-01-15",
            "from": "B", "text": "answer", "reply_to_message_id": 1,
        },
    ]
    path = _make_export(raw_messages, tmp_path)
    messages = parse_export(path)

    assert messages[1].reply_to_id == 1
    assert messages[0].reply_to_id is None
