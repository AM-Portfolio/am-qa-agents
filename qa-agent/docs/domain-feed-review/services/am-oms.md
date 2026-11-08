# am-oms

- **Domain:** trade
- **Status:** active (enabled=True)
- **Priority:** 7
- **OpenAPI ops:** 16
- **Snapshot:** `services/am-oms/openapi.yaml`
- **Data-gen:** `templates/data-gen/service/am-oms` (business.yaml=True)

## Environment matrix (am-specs targets)

| Env | Base URL | Feed posture |
|-----|----------|--------------|
| dev | `https://am-dev.asrax.in/oms` | Full feed + mutating OK |
| preprod | `https://am-preprod.asrax.in/oms` | Sync + import; prefer read/replay |
| prod | `https://am.asrax.in/oms` | Read-only / must-work only |

## API groups

Wallets, positions, orders (create/list/cancel/replace)

## Gaps / next

flows: [] — wallet→positions→orders; create/cancel dig-only.
