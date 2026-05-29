"""Unit-level canary tests. Auto-tagged `unit` by tests/conftest.py."""


async def test_canary_async() -> None:
    """pytest-asyncio auto mode dispatches async tests correctly."""
    assert True


def test_canary_sync() -> None:
    """Plain sync tests execute under the same runner."""
    assert 1 + 1 == 2
