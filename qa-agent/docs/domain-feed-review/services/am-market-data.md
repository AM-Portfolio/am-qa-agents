# am-market-data

- **Domain:** market
- **Status:** active (enabled=True)
- **Priority:** 1
- **OpenAPI ops:** 104
- **Snapshot:** `services/am-market-data/openapi.yaml`
- **Data-gen:** `templates/data-gen/service/am-market-data` (business.yaml=True)

## Environment matrix (am-specs targets)

| Env | Base URL | Feed posture |
|-----|----------|--------------|
| dev | `https://am-dev.asrax.in/market` | Full feed + mutating OK |
| preprod | `https://am-preprod.asrax.in/market` | Sync + import; prefer read/replay |
| prod | `https://am.asrax.in/market` | Read-only / must-work only |

## API groups

Quotes/LTP/OHLC, instruments, indices, watchlists, fundamentals, IPO, MF, streaming

## Gaps / next

Promote 6 composed flows into durable qa-agent pack; repair onboard openapi_sync flakiness.
