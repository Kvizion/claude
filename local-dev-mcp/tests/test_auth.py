"""Tests for the network transport token-auth middleware."""

import pytest

pytest.importorskip("starlette")

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from utils.auth import wrap_with_auth

TOKEN = "s3cret-token"


def _app():
    async def ok(request):
        return PlainTextResponse("ok")

    inner = Starlette(routes=[Route("/mcp", ok, methods=["GET", "POST"])])
    return wrap_with_auth(inner, TOKEN)


def test_missing_token_is_rejected():
    client = TestClient(_app())
    assert client.get("/mcp").status_code == 401


def test_wrong_token_is_rejected():
    client = TestClient(_app())
    assert client.get("/mcp", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/mcp", headers={"X-API-Key": "nope"}).status_code == 401


def test_correct_bearer_token_is_accepted():
    client = TestClient(_app())
    resp = client.get("/mcp", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_correct_api_key_header_is_accepted():
    client = TestClient(_app())
    resp = client.get("/mcp", headers={"X-API-Key": TOKEN})
    assert resp.status_code == 200


def test_correct_query_key_is_accepted():
    client = TestClient(_app())
    assert client.get(f"/mcp?key={TOKEN}").status_code == 200
    assert client.get(f"/mcp?token={TOKEN}").status_code == 200


def test_wrong_query_key_is_rejected():
    client = TestClient(_app())
    assert client.get("/mcp?key=nope").status_code == 401
