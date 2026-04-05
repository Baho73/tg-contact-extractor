import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx

from src.config import AppConfig
from src.extractor import (
    ContactField,
    ContactRecord,
    extract_contacts,
    _format_batch_for_prompt,
    _parse_llm_response,
)
from src.parser import Message


def _msg(id: int, text: str = "test") -> Message:
    return Message(id=id, date="2026-01-15", from_user="User", from_id=None, text=text, reply_to_id=None)


def _config() -> AppConfig:
    return AppConfig(openrouter_api_key="test-key", model="test/model")


class TestFormatBatch:
    def test_format(self):
        batch = [_msg(1, "hello"), _msg(2, "world")]
        text = _format_batch_for_prompt(batch)
        assert "[ID:1]" in text
        assert "[ID:2]" in text
        assert "hello" in text
        assert "world" in text


class TestParseLLMResponse:
    def test_parse_contacts_object(self):
        raw = json.dumps({
            "contacts": [
                {
                    "source_message_id": 1,
                    "from_user": "Alice",
                    "context": "shared phone",
                    "extracted": [
                        {"type": "телефон", "value": "+7 999 000 00 00"},
                        {"type": "ФИО", "value": "Иванов Пётр"},
                    ],
                }
            ]
        })
        records = _parse_llm_response(raw)
        assert len(records) == 1
        assert records[0].source_message_id == 1
        assert len(records[0].extracted) == 2
        assert records[0].extracted[0].type == "телефон"

    def test_parse_empty(self):
        raw = json.dumps({"contacts": []})
        records = _parse_llm_response(raw)
        assert records == []

    def test_parse_direct_array(self):
        raw = json.dumps([
            {
                "source_message_id": 5,
                "from_user": "Bob",
                "context": "email",
                "extracted": [{"type": "email", "value": "bob@test.com"}],
            }
        ])
        records = _parse_llm_response(raw)
        assert len(records) == 1
        assert records[0].extracted[0].value == "bob@test.com"

    def test_parse_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_response("not json {{{")


class TestExtractContacts:
    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "contacts": [{
                            "source_message_id": 1,
                            "from_user": "Test",
                            "context": "test",
                            "extracted": [{"type": "телефон", "value": "+7 000"}],
                        }]
                    })
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        batch = [_msg(1, "мой телефон +7 000")]
        contacts = await extract_contacts(batch, _config(), mock_client)

        assert len(contacts) == 1
        assert contacts[0].extracted[0].type == "телефон"

    @pytest.mark.asyncio
    async def test_empty_response(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"contacts": []}'}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        contacts = await extract_contacts([_msg(1, "просто тек��т")], _config(), mock_client)
        assert contacts == []
