"""Tests for prompt management functions in src.extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.extractor import list_prompts, load_prompt, save_prompt


# ---------------------------------------------------------------------------
# save + load round-trip
# ---------------------------------------------------------------------------


def test_save_and_load_prompt(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.extractor._prompts_dir", lambda: tmp_path)

    save_prompt("my_prompt", "Hello, this is a test prompt.")
    loaded = load_prompt("my_prompt")
    assert loaded == "Hello, this is a test prompt."


# ---------------------------------------------------------------------------
# list_prompts
# ---------------------------------------------------------------------------


def test_list_prompts(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.extractor._prompts_dir", lambda: tmp_path)

    save_prompt("beta", "prompt beta")
    save_prompt("alpha", "prompt alpha")

    names = list_prompts()
    assert names == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# load nonexistent raises
# ---------------------------------------------------------------------------


def test_load_nonexistent_raises(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.extractor._prompts_dir", lambda: tmp_path)

    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist")


# ---------------------------------------------------------------------------
# save creates directory
# ---------------------------------------------------------------------------


def test_save_creates_directory(tmp_path: Path, monkeypatch):
    sub = tmp_path / "sub"
    monkeypatch.setattr("src.extractor._prompts_dir", lambda: sub)

    assert not sub.exists()
    save_prompt("new_prompt", "content here")
    assert sub.exists()
    assert (sub / "new_prompt.txt").read_text(encoding="utf-8") == "content here"
