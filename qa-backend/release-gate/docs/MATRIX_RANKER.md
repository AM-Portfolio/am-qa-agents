# Matrix ranker (§23.3)

Deterministic. ChangeIntent is **advisory only**.

```
for each candidate in (impact_symbols ∪ load_rules ∪ smoke_defaults ∪ SPT):
  score = 0
  score += impact_tier_weight[tier]          # blast radius from GitNexus
  score += path_match_bonus(load_rules)      # repo/path → service/profile
  score += spt_priority(catalog)             # playbook priority
  if ChangeIntent.suggested_test_focus aligns with same service/repo:
    score += advisory_boost                  # small; never promotes to P0 alone
  if gnx_mode == degraded:
    score = max(score, smoke_floor)          # L3 floor
rank by score DESC; assign tiers P0/P1/P2 from release-policy.yaml
P0 = release_blocker; must pass for feature_clean
```

Implementation: `src/am_qa_agent/intelligence/matrix.py`  
Thresholds: `config/release-policy.yaml` → `matrix.tier_thresholds`
