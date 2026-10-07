# skill: happy_flow

## Intent
Prove the primary success path for this service ends in success using paths from **this service's** `api_surface`.

## Must include
- auth: follow the service invent profile (`default_auth`, usually `user_jwt`; `none` only for documented public reads)
- negative: false
- expected_status: 2xx on asserting steps (typically 200)
- 2–4 steps that form one coherent business flow for **this** service (not another service)

## Must not
- Must not assert 4xx/5xx as success
- Must not use Keycloak/helper/banned paths
- Must not copy another service's domains (e.g. do not invent subscription flows for identity)

## Diversity hints (specialize via service invent profile)
1. Primary list/read then current-resource read
2. Health/readiness (if on surface) then primary read
3. Alternate primary read order from service `skill_overlays.happy_flow`

## Example skeleton (replace paths from api_surface)
{"skill":"happy_flow","auth":"user_jwt","negative":false,"steps":[{"method":"get","path":"/<primary>","expected_status":200},{"method":"get","path":"/<current>","expected_status":200}]}
