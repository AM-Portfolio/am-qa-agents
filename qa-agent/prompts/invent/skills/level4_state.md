# skill: level4_state

## Intent
Prove multi-step state machine transitions for **this** service's lifecycle (as named in invent profile).

## Must include
- auth: per invent profile
- negative: false
- expected_status: 2xx on each legal transition
- 3+ steps showing state changes using only this service's surface

## Must not
- Must not jump illegal transitions without expecting 4xx (illegal = level5_abuse)
- Must not be a single GET

## Diversity hints (specialize via service invent profile)
1. Full happy lifecycle chain from invent profile
2. Alternate lifecycle (create → cancel, enable → disable, etc.)
3. Pause/hold then resume/restore if those verbs exist on surface

## Example skeleton
{"skill":"level4_state","auth":"user_jwt","negative":false,"steps":[{"method":"post","path":"/<state-a>","expected_status":200},{"method":"get","path":"/<current>","expected_status":200},{"method":"post","path":"/<state-b>","expected_status":200}]}
