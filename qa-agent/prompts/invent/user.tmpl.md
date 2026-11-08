service={{service}} env={{env}}
skills={{skills_json}}
scenarios_per_skill={{scenarios_per_skill}}
schema_version={{schema_version}}

## Service invent profile (THIS service — bind all scenarios here)
{{service_profile}}

## Platform skill playbooks (semantics — follow exactly)
{{playbooks}}

## Service skill overlays (specialize diversity / paths for THIS service)
{{skill_overlays}}

## api_surface (ONLY these method+path lines)
{{api_surface}}

## bans (never use these paths)
{{bans}}

## plugin catalogs (context only)
{{catalog}}

## existing scenarios (avoid duplicate path sequences / dedupe_keys)
{{existing}}

Invent up to {{scenarios_per_skill}} distinct, meaningful scenarios per skill in skills[]
for service={{service}} only. Return ONLY the JSON array.
