# Flows review inventory

Env allowance legend:

- **all** — safe on dig / preprod / prod (reads / health)
- **nonprod** — dig + preprod
- **dev-only** — mutating / upload / order create

## Per-service flows

### am-market-data (promote existing — all unless noted)

| id | steps | env |
|----|-------|-----|
| watchlist_to_ltp | list watchlists → items → live-ltp | all |
| index_quote_cluster | indices → ltp → quotes → ohlc | all |
| open_ipo_to_detail | open IPOs → counts → detail | all |
| search_to_fundamentals | instrument search → fundamentals | all |
| mf_detail_to_history | MF detail → history | all |
| watchlist_create_to_items | create watchlist → add item | dev-only |

### am-news

| id | steps | env |
|----|-------|-----|
| health_to_current_affairs | GET /health → GET /v1/current-affairs | all |
| holdings_news | GET /v1/holdings | all |
| admin_feed_smoke | GET /v1/admin/feed | nonprod |

### am-parser

| id | steps | env |
|----|-------|-----|
| list_jobs_smoke | GET /v1/?user_id=… | all |
| job_status_poll | GET /v1/{job_id}/status | all |
| upload_to_status | upload → poll status (when upload op seeded) | dev-only |

### am-portfolio

| id | steps | env |
|----|-------|-----|
| list_portfolios_to_holdings | GET /v1/portfolios → GET /v1/portfolios/holdings | all |
| basket_catalog_to_my | GET /v1/basket/catalog → GET /v1/basket/my | all |
| family_accounts_hub | GET /v1/portfolios/accounts-hub → family-members | all |
| stress_all_smoke | GET /v1/analytics/portfolio/all/stress | all |

### am-analysis

| id | steps | env |
|----|-------|-----|
| allocation_to_movers | allocation → performance → entity top-movers → type top-movers | all |

### am-trade-management-service

| id | steps | env |
|----|-------|-----|
| replay_date_range | GET trade-replays/date-range | all |
| replay_by_symbol | GET trade-replays/symbol/{symbol} | all |

### am-oms

| id | steps | env |
|----|-------|-----|
| health_to_wallets | /health → /v1/wallets | all |
| wallet_to_positions | wallet → positions → orders list | all |
| order_create_cancel | create order → cancel | dev-only |

### am-subscription

| id | steps | env |
|----|-------|-----|
| plans_to_me | /health → /subscriptions/plans → /subscriptions/me | all |
| usage_and_referrals | usage/history → referrals/me | all |

## Cross-domain (first feed: 2)

| id | services | steps | env |
|----|----------|-------|-----|
| xd_market_search_to_portfolio_holdings | market-data → portfolio | search_to_fundamentals bind → portfolios/holdings | nonprod |
| xd_parser_jobs_to_portfolio | parser → portfolio | list jobs → portfolios list | dev-only |

## Approval

- [ ] Per-service flow names OK  
- [ ] Env gates OK  
- [ ] Cross-domain pair OK for first feed  
