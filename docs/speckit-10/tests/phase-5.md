# Tests — Phase 5 (publish after E2E go)

**Verify:** GitHub MCP + packages + [E2E_PROD.md](../E2E_PROD.md).

- [x] Early pilots: `publish_github_packages.py` after E2E GO on `sdk-changed` (push) — Java jar + Python whl + Dart tar.gz under repo Packages
- [ ] Publish runs **only** for detect-changed services
- [ ] Publish job **requires** e2e-changed green (fail if skipped/red)
- [ ] Sample service: contract + Java + Python + Dart + MCP all go
- [ ] Unchanged services: no new package versions
- [ ] Tenant dry-run documented
- [ ] Scorecard: Prod E2E = 10; overall **10.0**
