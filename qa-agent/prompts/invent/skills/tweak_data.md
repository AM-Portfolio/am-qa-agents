# skill: tweak_data

## Intent
Prove a small legitimate mutation on **this** service changes observable state (mutate → read back).

## Must include
- auth: per invent profile (usually user_jwt)
- negative: false
- expected_status: 2xx on mutate and follow-up read
- At least one mutating method from api_surface, then a GET observe path from invent profile

## Must not
- Must not skip the read-back step
- Must not mutate another service's resources

## Diversity hints (specialize via service invent profile)
1. Primary mutate then current-resource GET
2. Alternate mutate then GET
3. Soft state change (pause/disable/update) then GET

## Example skeleton
{"skill":"tweak_data","auth":"user_jwt","negative":false,"steps":[{"method":"post","path":"/<mutate>","expected_status":200},{"method":"get","path":"/<current>","expected_status":200}]}
