"""Probe subscription health/plans/me with dig vs prod tokens."""
from __future__ import annotations

import os
from pathlib import Path

import httpx


def _load_dotenv() -> None:
    for p in (Path(__file__).resolve().parents[1] / ".env", Path.cwd() / ".env"):
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    _load_dotenv()
    user = (os.environ.get("SPT_AUTH_USERNAME") or "").strip()
    password = os.environ.get("SPT_AUTH_PASSWORD") or ""
    print("user", (user[:8] + "...") if user else "(empty)")
    c = httpx.Client(timeout=30.0)
    pairs = [
        ("dev", "https://am-dev.asrax.in/identity", "https://am-dev.asrax.in"),
        ("prod", "https://am.asrax.in/identity", "https://am.asrax.in"),
        ("cross dig→prod", "https://am-dev.asrax.in/identity", "https://am.asrax.in"),
    ]
    for label, id_host, sub_host in pairs:
        lr = c.post(
            f"{id_host}/auth/login",
            json={"username": user, "password": password},
        )
        print(label, "login", lr.status_code)
        if lr.status_code != 200:
            print(" ", lr.text[:160])
            continue
        tok = lr.json().get("access_token")
        h = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}
        for p in (
            "/subscriptions/health",
            "/subscriptions/plans",
            "/subscriptions/me",
        ):
            r = c.get(sub_host + p, headers=h)
            print(
                f"  {p} -> {r.status_code} {r.text[:100].replace(chr(10), ' ')}"
            )


if __name__ == "__main__":
    main()
