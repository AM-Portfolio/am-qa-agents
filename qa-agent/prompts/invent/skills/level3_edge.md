# skill: level3_edge

## Intent
Prove awkward but legal edge inputs for **this** service (boundary values, idempotent re-apply, unusual valid combinations).

## Must include
- auth: per invent profile
- negative: false unless invent profile documents soft-fail 4xx for that edge
- expected_status set explicitly
- Use entities/fields named in the service invent profile

## Must not
- Must not be random abuse/flood (level5_abuse)
- Must not omit expected_status

## Diversity hints (specialize via service invent profile)
1. Re-apply same transition/idempotent update
2. Resume/enable when already active (or service equivalent)
3. Boundary query/page size if surface supports it

## Example skeleton
{"skill":"level3_edge","auth":"user_jwt","negative":false,"steps":[{"method":"post","path":"/<transition>","body":{},"expected_status":200}]}
