# Auth / User / Subscription — detailed flow testing catalog

Source of truth for **UI Feature Scenarios** + **API OpenAPI tools** covering registration,
login, forgot/reset password, Google OAuth, sessions/logout, profile, and subscription.

## Env gates

| Gate | Meaning |
|------|---------|
| `prod_safe` | Safe on prod (read / soft UI / no account create) |
| `ephemeral_user` | Throwaway register → test pack → `request-deletion` cleanup |
| `nonprod_only` | Legacy alias — prefer `ephemeral_user` + GrowthBook |
| `manual_oauth` | Stops before Google credentials; human completes OAuth |

### GrowthBook: `qa-auth-ephemeral-user-flows`

Enables **FLOW_EPHEMERAL_SETUP** (register+login), **FLOW_LOGOUT_ALL_DEVICES**,
**FLOW_SUBSCRIPTION** (with throwaway token), and **FLOW_EPHEMERAL_CLEANUP**.

| Env | Default when flag unset / GB unavailable |
|-----|------------------------------------------|
| dev / preprod | **on** |
| prod | **on for now** (disable later in GrowthBook) |

Overrides (any of): `FLOW_EPHEMERAL_USER=0|1`, `QA_AUTH_EPHEMERAL_USER_FLOWS=0|1`,
`QA_FLAG_QA_AUTH_EPHEMERAL_USER_FLOWS=0|1`.

GB config: `GROWTHBOOK_API_HOST` / `GB_API_URL` + `GROWTHBOOK_CLIENT_KEY` or
`GROWTHBOOK_API_KEY` / `GB_API_KEY`.

Ephemeral login needs email verify. Runner force-verifies via Keycloak admin when
`KEYCLOAK_URL` + `KEYCLOAK_ADMIN` + `KEYCLOAK_ADMIN_PASSWORD` + `KEYCLOAK_REALM`
are set (loaded from `~/.asrax/credentials.d/infra.env` when present). Cleanup =
`POST /users/me/request-deletion`, with Keycloak disable as fallback.

## Module suites

| Suite id | Contents |
|----------|----------|
| `auth_user_module` | Existing Cucumber UI auth (reg → login → forgot → Google) |
| `auth_user_full_flows` | Full UI flow pack below |
| `auth_api_module` | Identity API smoke (health/login/discover) |
| `auth_user_api_flows` | Detailed API flows (login → sessions → logout…) |

---

## 1. Registration (create user)

| Id | Layer | Gate | Steps |
|----|-------|------|-------|
| `AUTH_REG_OPEN` | UI | prod_safe | Open `/register`, see form |
| `AUTH_REG_VALIDATION` | UI | prod_safe | Empty submit → validation |
| `AUTH_REG_FILL` | UI | prod_safe | Fill unique `qa+…` email — **do not submit on prod** |
| `AUTH_REG_SUBMIT_NONPROD` | UI | nonprod_only | Submit Create Account → success / verify-email |
| `API_AUTH_REGISTER` | API | nonprod_only | `POST /auth/register` with unique email |
| `API_AUTH_VERIFY_EMAIL_RESEND` | API | nonprod_only | `POST /auth/verify-email/resend` |

## 2. Login

| Id | Layer | Gate | Steps |
|----|-------|------|-------|
| `AUTH_LOGIN_OK` | UI | prod_safe | Credentials → `/app/dashboard` |
| `AUTH_LOGIN_BAD_PW` | UI | prod_safe | Wrong password → error |
| `AUTH_LOGIN_CREDS_ONLY` | UI | prod_safe | Form ready; no Demo Login |
| `API_AUTH_LOGIN` | API | prod_safe | `POST /auth/login` → access_token |
| `API_AUTH_REFRESH` | API | prod_safe | `POST /auth/refresh` with refresh_token |
| `API_AUTH_STEP_UP` | API | nonprod_only | Step-up when required |

## 3. Forgot / reset password

| Id | Layer | Gate | Steps |
|----|-------|------|-------|
| `AUTH_FORGOT_OPEN` | UI | prod_safe | Open `/forgot-password` |
| `AUTH_FORGOT_SUBMIT` | UI | prod_safe | Submit reset for TEST_USER email (idempotent UX) |
| `API_AUTH_PASSWORD_RESET` | API | prod_safe | `POST /auth/password-reset` (request only) |
| `API_AUTH_PASSWORD_RESET_CONFIRM` | API | nonprod_only | `POST /auth/password-reset/confirm` with token |
| `AUTH_RESET_PAGE_OPEN` | UI | prod_safe | Open `/reset-password` shell (token soft) |

## 4. Google login

| Id | Layer | Gate | Steps |
|----|-------|------|-------|
| `AUTH_GOOGLE_CTA` | UI | prod_safe | See Continue with Google |
| `AUTH_GOOGLE_REDIRECT` | UI | manual_oauth | Click CTA → Google host (stop before password) |
| `API_AUTH_GOOGLE_URL` | API | prod_safe | `POST /auth/google/url` → auth_url + state |
| `API_AUTH_GOOGLE_TOKEN` | API | manual_oauth | Exchange code (manual) |

## 5. Sessions / logout / logout all devices

| Id | Layer | Gate | Steps |
|----|-------|------|-------|
| `AUTH_SESSIONS_LIST_UI` | UI | prod_safe | Login → Profile/Privacy → see sessions chrome (soft) |
| `API_USERS_SESSIONS_LIST` | API | prod_safe | `GET /users/me/login-sessions` |
| `API_USERS_SECURITY_EVENTS` | API | prod_safe | `GET /users/me/security-events` |
| `API_AUTH_LOGOUT` | API | prod_safe* | `POST /auth/logout` (*uses disposable login) |
| `API_USERS_REVOKE_SESSION` | API | nonprod_only | `DELETE /users/me/login-sessions/{id}` |
| `API_USERS_LOGOUT_ALL` | API | nonprod_only | `DELETE /users/me/login-sessions` (all devices) |
| `AUTH_LOGOUT_UI` | UI | prod_safe | Login → open account menu → Sign out → back to login |

\* Logout API: login first in the same flow, then logout that token (does not kill portal SPT creds permanently).

## 6. Profile / settings / me

| Id | Layer | Gate | Steps |
|----|-------|------|-------|
| `API_USERS_ME` | API | prod_safe | `GET /users/me` (track prod 500 as defect) |
| `API_USERS_SETTINGS_PATCH` | API | nonprod_only | `PATCH /users/me/settings` |
| `AUTH_PROFILE_SMOKE` | UI | prod_safe | Existing `PROFILE_SMOKE_FLOW` |

## 7. Subscription / plans / time left

| Id | Layer | Gate | Steps |
|----|-------|------|-------|
| `SUB_UI_OPEN` | UI | prod_safe | Login → `/app/subscription` — Plan / Upgrade |
| `SUB_UI_TIME_LEFT` | UI | prod_safe | Soft assert trial/renewal/time-left copy |
| `SUB_UI_PLANS` | UI | prod_safe | Soft assert plan cards / Free / Pro |
| `API_SUB_HEALTH` | API | prod_safe | When subscription OpenAPI is reachable |
| `API_SUB_ME` | API | prod_safe | Current subscription + expires / trial fields |
| `API_SUB_PLANS` | API | prod_safe | List plans |

> Prod subscription Swagger is currently behind Flutter HTML at `/subscription/openapi.json`.
> UI flows are primary until gateway exposes JSON OpenAPI; API rows activate when fetch succeeds.

## 8. End-to-end journey (orchestration)

| Journey | Order |
|---------|-------|
| **J1 Happy path (prod_safe)** | Google CTA → Login OK → Sessions list → Subscription open → Logout UI |
| **J2 Recovery** | Forgot open → Forgot submit → Login OK |
| **J3 Ephemeral lifecycle** | `FLOW_EPHEMERAL_SETUP` → sessions/logout-all/subscription → `FLOW_EPHEMERAL_CLEANUP` |
| **J4 OAuth** | Google URL API → UI redirect (manual complete) |

---

## How to run

```bash
# Complete auth + users + subscription (UI + API) → one combined report
cd qa-agent
set PYTHONPATH=.
python -u ui_evidence/scripts/run_auth_module_complete.py
python -u ui_evidence/scripts/run_auth_module_complete.py --open-report

# UI suites only
python -u ui_evidence/scripts/run_suite.py --suite auth_users_subs_module --login-mode credentials
python -u ui_evidence/scripts/run_suite.py --suite auth_user_full_flows --login-mode credentials

# API detailed flows (Hotspots + metrics ledger)
python -u ui_evidence/api/run_auth_user_api_flows.py

# API users / user-platform / subscription sweep
python -u ui_evidence/api/run_all_auth_user_apis.py
```

### Reports

| File | What |
|------|------|
| `ui_evidence/data/reports/api-test/auth-module-complete-latest.html` | **Combined** UI + API flows + sweep + Hotspots |
| `…/auth-user-api-flows-latest.html` | Detailed API flows (+ Hotspots) |
| `…/auth-user-apis-latest.html` | Users / subscription OpenAPI sweep |
| `…/auth-user-api-flows-metrics.json` | Rolling fail/skip/duration ledger |
| `REPORT_DIR/suite-*.json` | UI suite rollup; per-profile HTML linked from combined report |

Suite ids: `auth_user_module`, `auth_user_full_flows`, **`auth_users_subs_module`** (full flows + `PROFILE_SMOKE_FLOW` + `SUBSCRIPTION_SMOKE_FLOW`).
