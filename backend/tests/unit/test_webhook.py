from __future__ import annotations

import hashlib
import hmac
import json
import os

os.environ.setdefault("MT5_MOCK", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("TRADER_PASSWORD", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("REDIS_PASSWORD", "test")

import pytest
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


VALID_PAYLOAD = {
    "symbol": "XAUUSD",
    "action": "buy",
    "price": 2300.5,
    "strategy": "ema_macd",
}


def test_webhook_no_secret_accepts_payload(monkeypatch):
    """Without a configured secret, any request is accepted."""
    monkeypatch.setattr("app.api.webhooks.tradingview.settings.tradingview_webhook_secret", "")
    body = json.dumps(VALID_PAYLOAD).encode()
    resp = client.post("/webhook/tradingview", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert resp.json()["symbol"] == "XAUUSD"


def test_webhook_valid_signature_accepted(monkeypatch):
    secret = "test-webhook-secret"
    monkeypatch.setattr("app.api.webhooks.tradingview.settings.tradingview_webhook_secret", secret)
    body = json.dumps(VALID_PAYLOAD).encode()
    sig = _sign(body, secret)
    resp = client.post(
        "/webhook/tradingview",
        content=body,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
    )
    assert resp.status_code == 200


def test_webhook_invalid_signature_rejected(monkeypatch):
    secret = "test-webhook-secret"
    monkeypatch.setattr("app.api.webhooks.tradingview.settings.tradingview_webhook_secret", secret)
    body = json.dumps(VALID_PAYLOAD).encode()
    resp = client.post(
        "/webhook/tradingview",
        content=body,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": "wrong"},
    )
    assert resp.status_code == 401


def test_webhook_missing_signature_rejected(monkeypatch):
    secret = "test-webhook-secret"
    monkeypatch.setattr("app.api.webhooks.tradingview.settings.tradingview_webhook_secret", secret)
    body = json.dumps(VALID_PAYLOAD).encode()
    resp = client.post("/webhook/tradingview", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


def test_webhook_invalid_action_rejected(monkeypatch):
    monkeypatch.setattr("app.api.webhooks.tradingview.settings.tradingview_webhook_secret", "")
    body = json.dumps({"symbol": "XAUUSD", "action": "invalid_action"}).encode()
    resp = client.post("/webhook/tradingview", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 422


def test_webhook_symbol_uppercased(monkeypatch):
    monkeypatch.setattr("app.api.webhooks.tradingview.settings.tradingview_webhook_secret", "")
    body = json.dumps({"symbol": "xauusd", "action": "sell"}).encode()
    resp = client.post("/webhook/tradingview", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "XAUUSD"


def test_webhook_close_all_action(monkeypatch):
    monkeypatch.setattr("app.api.webhooks.tradingview.settings.tradingview_webhook_secret", "")
    body = json.dumps({"symbol": "EURUSD", "action": "close_all"}).encode()
    resp = client.post("/webhook/tradingview", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 200
