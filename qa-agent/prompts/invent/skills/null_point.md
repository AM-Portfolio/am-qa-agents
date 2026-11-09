# skill: null_point

## Intent
Prove missing/unknown resources for **this** service yield not-found or empty behavior.

## Must include
- auth: per invent profile
- negative: true
- expected_status: 404 preferred (or documented empty 200 only if invent profile says so)
- Path referencing a clearly nonexistent id from invent profile `null_ids` / fake slug

## Must not
- Must not use real happy ids from prep
- Must not confuse with 401/403 (security)

## Diversity hints (specialize via service invent profile)
1. GET detail with fake id
2. Mutate unknown resource id
3. Internal check for unknown subject if on surface

## Example skeleton
{"skill":"null_point","auth":"user_jwt","negative":true,"steps":[{"method":"get","path":"/<resource>/does-not-exist-xyz","expected_status":404}]}
