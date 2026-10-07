# skill: validation

## Intent
Prove bad or incomplete input on **this service's** mutate/create endpoints is rejected with a client error.

## Must include
- auth: per invent profile (usually user_jwt or service_token for internal APIs)
- negative: true
- expected_status: 400 or 422 on the asserting step
- Body empty / wrong type / missing required fields for a real mutate path on api_surface

## Must not
- Must not expect 2xx
- Must not label missing-auth as validation (use security)
- Must not invent paths outside api_surface

## Diversity hints (specialize via service invent profile)
1. Create/update with empty JSON
2. Mutate with invalid id/field types from invent profile entities
3. Internal check/meter with missing required field if on surface

## Example skeleton
{"skill":"validation","auth":"user_jwt","negative":true,"steps":[{"method":"post","path":"/<mutate>","body":{},"expected_status":400}]}
