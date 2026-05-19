"""Tests for remote difficulty table fetching."""
from __future__ import annotations

import httpx
import pytest

from app.parsers.table_fetcher import fetch_table


@pytest.mark.asyncio
async def test_fetch_table_resolves_relative_header_after_redirect() -> None:
    """Relative bmstable URLs should use the final redirected page URL."""

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://example.com/table":
            return httpx.Response(301, headers={"Location": "https://example.com/table/"})
        if url == "https://example.com/table/":
            return httpx.Response(
                200,
                text='<html><head><meta name="bmstable" content="header.json"></head></html>',
            )
        if url == "https://example.com/table/header.json":
            return httpx.Response(200, json={"name": "Redirected", "data_url": "data.json"})
        if url == "https://example.com/table/data.json":
            return httpx.Response(
                200,
                json=[{"md5": "a" * 32, "level": "1", "title": "Song A"}],
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    ) as client:
        table = await fetch_table("https://example.com/table", client=client)

    assert table["header"]["name"] == "Redirected"
    assert table["songs"][0]["md5"] == "a" * 32


@pytest.mark.asyncio
async def test_fetch_table_decodes_html_entities_in_display_text() -> None:
    """External table JSON should not persist HTML entities in display text."""

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://example.com/header.json":
            return httpx.Response(200, json={"name": "Entity Table", "data_url": "data.json"})
        if url == "https://example.com/data.json":
            return httpx.Response(
                200,
                json=[
                    {
                        "md5": "b" * 32,
                        "level": "1",
                        "title": "lack &quot;0&quot; clock",
                        "artist": "Alice &amp; Bob",
                    }
                ],
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    ) as client:
        table = await fetch_table("https://example.com/header.json", client=client)

    assert table["songs"][0]["title"] == 'lack "0" clock'
    assert table["songs"][0]["artist"] == "Alice & Bob"
