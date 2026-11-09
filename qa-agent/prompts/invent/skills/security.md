# skill: security

## Intent
Prove **this service's** protected routes reject missing or wrong auth (not a happy login flow).

## Must include
- auth: none (or invent profile `wrong_auth` note)
- negative: true
- expected_status: 401 or 403 on a protected path listed in invent profile `protected_paths` / api_surface
- Call a protected path WITHOUT valid credentials

## Must not
- Must not invent successful login+me and call it security
- Must not use Keycloak/token-helper as the scenario under test
- Must not expect 2xx

## Diversity hints (specialize via service invent profile)
1. Primary protected GET with auth=none → 401
2. Current-resource GET with auth=none → 401
3. Mutating POST with auth=none → 401/403

## Example skeleton
{"skill":"security","auth":"none","negative":true,"steps":[{"method":"get","path":"/<protected>","expected_status":401}]}
