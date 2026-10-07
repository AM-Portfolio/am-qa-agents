"""Phase 3 — hand-seeded data_prep fail-closed + assert_only (no live SPT)."""
from __future__ import annotations

from ui_evidence.scenario_bank import data_prep


def _id_tools():
    return [
        {
            "name": "am-identity.post.auth.login",
            "path": "/auth/login",
            "method": "post",
        }
    ]


def _sub_tools(*, with_grant: bool = True):
    tools = [
        {
            "name": "am-subscription.get.plans",
            "path": "/plans",
            "method": "get",
        },
        {
            "name": "am-subscription.get.me",
            "path": "/subscriptions/me",
            "method": "get",
        },
    ]
    if with_grant:
        tools.append(
            {
                "name": "am-subscription.post.ensure-trial",
                "path": "/admin/ensure-trial",
                "method": "post",
            }
        )
    return tools


def test_dev_fail_closed_when_auth_missing(monkeypatch):
    monkeypatch.delenv("SPT_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("SPT_AUTH_PASSWORD", raising=False)

    def list_tools_fn(**kwargs):
        svc = kwargs.get("service")
        if svc == "am-identity":
            return {"tools": _id_tools()}
        return {"tools": _sub_tools()}

    calls: list[str] = []

    def call_tool(name, *args, **kwargs):
        calls.append(name)
        return {"ok": True, "status": 200, "body": {}}

    out = data_prep.prepare_subscription(
        env="dev",
        assert_only=False,
        refresh=False,
        call_tool=call_tool,
        list_tools_fn=list_tools_fn,
        refresh_fn=lambda **kw: {},
    )
    assert out["ok"] is False
    assert out["fail_closed"] is True
    assert out["env"] == "dev"
    assert calls == []
    assert any(s.get("id") == "login" and s.get("status") == "FAILED" for s in out["steps"])


def test_assert_only_never_calls_grant(monkeypatch):
    monkeypatch.setenv("SPT_AUTH_USERNAME", "qa@example.com")
    monkeypatch.setenv("SPT_AUTH_PASSWORD", "secret")

    def list_tools_fn(**kwargs):
        svc = kwargs.get("service")
        if svc == "am-identity":
            return {"tools": _id_tools()}
        return {"tools": _sub_tools(with_grant=True)}

    calls: list[str] = []

    def call_tool(name, payload=None, **kwargs):
        calls.append(str(name))
        if "login" in str(name).lower():
            return {
                "ok": True,
                "status": 200,
                "body": {"access_token": "t-assert"},
            }
        return {"ok": True, "status": 200, "body": {"ok": True}}

    out = data_prep.prepare_subscription(
        env="prod",
        assert_only=True,
        refresh=False,
        call_tool=call_tool,
        list_tools_fn=list_tools_fn,
        refresh_fn=lambda **kw: {},
    )
    assert out["assert_only"] is True
    assert out["ok"] is True
    ensure_step = next(s for s in out["steps"] if s["id"] == "ensure_grant")
    assert ensure_step["status"] == "SKIPPED"
    assert "assert_only" in ensure_step.get("reason", "")
    assert not any("ensure" in c.lower() or "grant" in c.lower() for c in calls)
    assert any("login" in c.lower() for c in calls)


def test_identity_fail_closed_dev(monkeypatch):
    monkeypatch.delenv("SPT_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("SPT_AUTH_PASSWORD", raising=False)

    out = data_prep.prepare_identity(
        env="dev",
        assert_only=False,
        refresh=False,
        call_tool=lambda *a, **k: {"ok": False},
        list_tools_fn=lambda **kw: {"tools": _id_tools()},
        refresh_fn=lambda **kw: {},
    )
    assert out["ok"] is False
    assert out["fail_closed"] is True


def test_dig_env_normalized_to_dev(monkeypatch):
    monkeypatch.delenv("SPT_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("SPT_AUTH_PASSWORD", raising=False)
    out = data_prep.prepare_subscription(
        env="dig",
        assert_only=False,
        refresh=False,
        call_tool=lambda *a, **k: {"ok": False},
        list_tools_fn=lambda **kw: {
            "tools": _id_tools() if kw.get("service") == "am-identity" else _sub_tools()
        },
        refresh_fn=lambda **kw: {},
    )
    assert out["env"] == "dev"
    assert out["fail_closed"] is True
