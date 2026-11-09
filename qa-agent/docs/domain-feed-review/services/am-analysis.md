# am-analysis

- **Domain:** portfolio
- **Status:** active (enabled=True)
- **Priority:** 5
- **OpenAPI ops:** 4
- **Snapshot:** `services/am-analysis/openapi.yaml`
- **Data-gen:** `templates/data-gen/service/am-analysis` (business.yaml=True)

## Environment matrix (am-specs targets)

| Env | Base URL | Feed posture |
|-----|----------|--------------|
| dev | `https://am-dev.asrax.in/analysis` | Full feed + mutating OK |
| preprod | `https://am-preprod.asrax.in/analysis` | Sync + import; prefer read/replay |
| prod | `https://am.asrax.in/analysis` | Read-only / must-work only |

## API groups

Allocation, performance, category/entity top movers

## Gaps / next

flows: [] — linear 4-op analysis flow; needs portfolio id binds.
