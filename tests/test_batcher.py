from src.batcher import estimate_tokens, make_batches
from src.parser import Message


def _msg(id: int, text: str = "test message") -> Message:
    return Message(id=id, date="2026-01-15", from_user="User", from_id=None, text=text, reply_to_id=None)


def test_empty_input():
    assert make_batches([]) == []


def test_single_batch():
    messages = [_msg(i) for i in range(10)]
    batches = make_batches(messages, batch_size=50, max_tokens=3000)
    assert len(batches) == 1
    assert len(batches[0]) == 10


def test_split_by_count():
    messages = [_msg(i) for i in range(120)]
    batches = make_batches(messages, batch_size=50, max_tokens=99999)
    assert len(batches) == 3
    assert len(batches[0]) == 50
    assert len(batches[1]) == 50
    assert len(batches[2]) == 20


def test_split_by_tokens():
    # Each message ~100 chars -> ~25 tokens + header
    long_text = "x" * 100
    messages = [_msg(i, long_text) for i in range(10)]
    batches = make_batches(messages, batch_size=999, max_tokens=100)
    # With ~30+ tokens per msg and max_tokens=100, should get multiple batches
    assert len(batches) > 1


def test_estimate_tokens():
    msg = _msg(1, "Hello world test")
    tokens = estimate_tokens(msg)
    assert tokens > 0
    assert isinstance(tokens, int)


def test_large_message_alone():
    # A single very large message should still produce a batch
    huge = _msg(1, "x" * 10000)
    batches = make_batches([huge], batch_size=50, max_tokens=100)
    assert len(batches) == 1
    assert len(batches[0]) == 1


def test_preserves_order():
    messages = [_msg(i, f"msg-{i}") for i in range(75)]
    batches = make_batches(messages, batch_size=50, max_tokens=99999)
    flat = [m for batch in batches for m in batch]
    assert [m.id for m in flat] == list(range(75))
