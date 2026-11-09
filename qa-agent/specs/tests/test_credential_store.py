"""Encrypted credential store — no secrets in public API."""
from __future__ import annotations

from pathlib import Path

import pytest

from specs.security import credential_store as cs


@pytest.fixture()
def cred_tmpdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cs.settings, "data_dir", str(tmp_path))
    monkeypatch.setenv("QA_CREDENTIALS_KEY", "test-key-for-unit")
    return tmp_path


def test_upsert_list_never_returns_secret(cred_tmpdir):
    pub = cs.upsert_credential(
        id="cred_test1",
        name="Test login",
        kind="identity_login",
        env="prod",
        username="user@example.com",
        password="super-secret",
    )
    assert pub["id"] == "cred_test1"
    assert pub["has_secret"] is True
    assert "password" not in pub
    assert "secret_enc" not in pub

    rows = cs.list_credentials()
    assert rows[0]["has_secret"] is True
    assert "password" not in rows[0]

    resolved = cs.resolve_credential("cred_test1")
    assert resolved is not None
    assert resolved["password"] == "super-secret"


def test_seed_from_spt_env(cred_tmpdir, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SPT_AUTH_USERNAME", "seed@example.com")
    monkeypatch.setenv("SPT_AUTH_PASSWORD", "seed-pass")
    monkeypatch.setattr(cs.settings, "spt_auth_username", "seed@example.com")
    monkeypatch.setattr(cs.settings, "spt_auth_password", "seed-pass")
    monkeypatch.setattr(cs.settings, "app_env", "prod")
    monkeypatch.setattr(cs.settings, "default_environment", "prod")

    rows = cs.seed_from_spt_env()
    assert rows
    assert rows[0]["username"] == "seed@example.com"
    again = cs.seed_from_spt_env()
    assert again[0]["id"] == rows[0]["id"]
