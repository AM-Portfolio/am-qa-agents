# skill: level5_abuse

## Intent
Prove illegal or abusive state toggles on **this** service are rejected safely.

## Must include
- auth: per invent profile
- negative: true
- expected_status: 4xx on the asserting abuse step (400/409/422)
- Sequence that attempts illegal transition or rapid conflicting mutates from invent profile

## Must not
- Must not expect 2xx on the abuse assertion
- Must not be a normal happy lifecycle
- Must not use Keycloak

## Diversity hints (specialize via service invent profile)
1. Double-apply terminal action (cancel/delete twice)
2. Resume/restore without prior pause/disable
3. Rapid conflicting mutate burst ending in 4xx

## Example skeleton
{"skill":"level5_abuse","auth":"user_jwt","negative":true,"steps":[{"method":"post","path":"/<terminal>","expected_status":200},{"method":"post","path":"/<terminal>","expected_status":409}]}
