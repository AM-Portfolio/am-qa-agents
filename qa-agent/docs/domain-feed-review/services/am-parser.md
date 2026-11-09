# am-parser

- **Domain:** market
- **Status:** active (enabled=True)
- **Priority:** 3
- **OpenAPI ops:** 29
- **Snapshot:** `services/am-parser/openapi.yaml`
- **Data-gen:** `templates/data-gen/service/am-parser` (business.yaml=True)

## Environment matrix (am-specs targets)

| Env | Base URL | Feed posture |
|-----|----------|--------------|
| dev | `https://am-dev.asrax.in/parser` | Full feed + mutating OK |
| preprod | `https://am-preprod.asrax.in/parser` | Sync + import; prefer read/replay |
| prod | `https://am.asrax.in/parser` | Read-only / must-work only |

## API groups

Excel/file parse jobs, ETF/MF holdings extraction

## Gaps / next

flows: [] — author upload→poll→holdings; mutating = dig only.
