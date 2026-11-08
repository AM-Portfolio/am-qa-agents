# am-trade-management-service

- **Domain:** trade
- **Status:** active (enabled=True)
- **Priority:** 6
- **OpenAPI ops:** 98
- **Snapshot:** `services/am-trade-management-service/openapi.yaml`
- **Data-gen:** `templates/data-gen/service/am-trade-management-service` (business.yaml=True)

## Environment matrix (am-specs targets)

| Env | Base URL | Feed posture |
|-----|----------|--------------|
| dev | `https://am-dev.asrax.in/trade` | Full feed + mutating OK |
| preprod | `https://am-preprod.asrax.in/trade` | Sync + import; prefer read/replay |
| prod | `https://am.asrax.in/trade` | Read-only / must-work only |

## API groups

Trades, journals, replays, metrics, heatmaps

## Gaps / next

flows: [] — list→detail→journal; replay read paths.
