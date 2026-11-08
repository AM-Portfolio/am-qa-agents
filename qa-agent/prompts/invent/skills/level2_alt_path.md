# skill: level2_alt_path

## Intent
Prove an alternate valid path to a similar outcome for **this** service (different endpoint order or secondary read on the same surface).

## Must include
- auth: per service invent profile
- negative: false
- expected_status: 2xx
- Path sequence different from happy_flow for this invent batch

## Must not
- Must not duplicate happy_flow step order
- Must not jump to unrelated services

## Diversity hints (specialize via service invent profile)
1. Reverse primary read order
2. Secondary resource (history/list/detail) then current
3. Internal/service_token alternate only if invent profile lists it

## Example skeleton
{"skill":"level2_alt_path","auth":"user_jwt","negative":false,"steps":[{"method":"get","path":"/<current>","expected_status":200},{"method":"get","path":"/<primary>","expected_status":200}]}
