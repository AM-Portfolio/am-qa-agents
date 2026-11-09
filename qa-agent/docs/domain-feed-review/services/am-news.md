# am-news

- **Domain:** market
- **Status:** active (enabled=True)
- **Priority:** 2
- **OpenAPI ops:** 11
- **Snapshot:** `services/am-news/openapi.yaml`
- **Data-gen:** `templates/data-gen/service/am-news` (business.yaml=True)

## Environment matrix (am-specs targets)

| Env | Base URL | Feed posture |
|-----|----------|--------------|
| dev | `https://am-dev.asrax.in/news` | Full feed + mutating OK |
| preprod | `https://am-preprod.asrax.in/news` | Sync + import; prefer read/replay |
| prod | `https://am.asrax.in/news` | Read-only / must-work only |

## API groups

Current affairs, holdings news, admin feed/replay

## Gaps / next

flows: [] — author health→affairs and holdings news flows.
