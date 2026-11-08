# am-portfolio

- **Domain:** portfolio
- **Status:** active (enabled=True)
- **Priority:** 4
- **OpenAPI ops:** 66
- **Snapshot:** `services/am-portfolio/openapi.yaml`
- **Data-gen:** `templates/data-gen/service/am-portfolio` (business.yaml=True)

## Environment matrix (am-specs targets)

| Env | Base URL | Feed posture |
|-----|----------|--------------|
| dev | `https://am-dev.asrax.in/portfolio` | Full feed + mutating OK |
| preprod | `https://am-preprod.asrax.in/portfolio` | Sync + import; prefer read/replay |
| prod | `https://am.asrax.in/portfolio` | Read-only / must-work only |

## API groups

Portfolios, holdings, baskets, snapshots, stress/what-if

## Gaps / next

flows: [] — author list→holdings→snapshot; UI flows exist only.
