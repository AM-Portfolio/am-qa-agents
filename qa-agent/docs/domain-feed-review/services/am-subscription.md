# am-subscription

- **Domain:** platform
- **Status:** active (enabled=True)
- **Priority:** 8
- **OpenAPI ops:** 19
- **Snapshot:** `services/am-subscription/openapi.yaml`
- **Data-gen:** `templates/data-gen/service/am-subscription` (business.yaml=True)

## Environment matrix (am-specs targets)

| Env | Base URL | Feed posture |
|-----|----------|--------------|
| dev | `https://am-dev.asrax.in/subscriptions` | Full feed + mutating OK |
| preprod | `https://am-preprod.asrax.in/subscriptions` | Sync + import; prefer read/replay |
| prod | `https://am.asrax.in/subscriptions` | Read-only / must-work only |

## API groups

Plans, me, usage, referrals, entitlements

## Gaps / next

Plugin pack exists; commit overview/payload fixture; add business.yaml flows.
