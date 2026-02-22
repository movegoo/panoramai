"""Tests for the FallbackChain."""
import pytest
from services.fallback import FallbackChain, FallbackResult


@pytest.mark.asyncio
async def test_primary_succeeds():
    """Primary succeeds → returns primary data."""
    async def ok():
        return {"followers": 1000, "bio": "hello"}

    chain = FallbackChain([("primary", ok)])
    result = await chain.execute()
    assert result.success
    assert result.source == "primary"
    assert result.data["followers"] == 1000


@pytest.mark.asyncio
async def test_primary_fails_fallback():
    """Primary fails → falls back to secondary."""
    async def fail():
        raise Exception("boom")

    async def ok():
        return {"followers": 500}

    chain = FallbackChain([("primary", fail), ("secondary", ok)])
    result = await chain.execute()
    assert result.success
    assert result.source == "secondary"
    assert result.data["followers"] == 500
    assert "primary: boom" in result.errors[0]


@pytest.mark.asyncio
async def test_complement_empty_fields():
    """Primary succeeds with empty fields → secondary complements."""
    async def partial():
        return {"followers": 1000, "bio": None, "engagement": None}

    async def complement():
        return {"followers": 0, "bio": "hello world", "engagement": 5.2}

    chain = FallbackChain([("primary", partial), ("complement", complement)])
    result = await chain.execute()
    assert result.success
    assert result.source == "primary"
    assert result.data["followers"] == 1000  # kept from primary
    assert result.data["bio"] == "hello world"  # from complement
    assert result.data["engagement"] == 5.2  # from complement
    assert "complement" in result.complemented_from


@pytest.mark.asyncio
async def test_all_fail():
    """All providers fail → result unsuccessful."""
    async def fail1():
        raise Exception("err1")

    async def fail2():
        raise Exception("err2")

    chain = FallbackChain([("a", fail1), ("b", fail2)])
    result = await chain.execute()
    assert not result.success
    assert len(result.errors) == 2


@pytest.mark.asyncio
async def test_stops_when_all_fields_filled():
    """Chain stops when all fields are filled."""
    call_count = 0

    async def full():
        nonlocal call_count
        call_count += 1
        return {"a": 1, "b": 2}

    async def extra():
        nonlocal call_count
        call_count += 1
        return {"a": 10, "b": 20}

    chain = FallbackChain([("full", full), ("extra", extra)])
    result = await chain.execute()
    assert result.success
    assert call_count == 1  # extra not called


@pytest.mark.asyncio
async def test_empty_response_skipped():
    """Provider returning empty dict is skipped."""
    async def empty():
        return {}

    async def ok():
        return {"data": 42}

    chain = FallbackChain([("empty", empty), ("ok", ok)])
    result = await chain.execute()
    assert result.success
    assert result.source == "ok"
