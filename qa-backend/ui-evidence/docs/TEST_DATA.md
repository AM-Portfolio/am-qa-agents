# Test data contract (ui-test-agent)

## Personas

| Persona | Login | Use |
|---------|-------|-----|
| `demo_user` | Demo Login | Default smoke; portfolio count may be 0..N |
| `credentials_user` | `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` | Stable preprod |
| `admin_user` | `TEST_ADMIN_EMAIL` / `TEST_ADMIN_PASSWORD` | Analysis / AI Chat |
| `sandbox_user` | credentials | Doc upload / write flows only |

Configured in [`catalog/test_data.yaml`](../catalog/test_data.yaml).

## Soft vs hard asserts

- **Hard:** URL/route, module load failures, error banners
- **Soft:** Data-dependent labels (Overview text when empty portfolio, etc.) → `GO_WITH_CAVEATS`

## Backends required

| Domain | Local | Preprod |
|--------|-------|---------|
| Dashboard / auth | am_app `:9000` + identity | `${AM_API_BASE_URL}` |
| Portfolio | + portfolio API | gateway |
| Market | + market API | gateway |
| Trade | + trade API | gateway |
| Doc Intel | + docs API | gateway |

## Fixed portfolio deep-links

Set `TEST_PORTFOLIO_ID` or target `portfolio_id` for 3-segment paths.

## Smoke CI knobs

```
DESIGN_REVIEW_ENABLED=false
SELF_HEAL_ENABLED=false
PLAYWRIGHT_TRACE=on-failure
STEP_RETRY_COUNT=1
```
