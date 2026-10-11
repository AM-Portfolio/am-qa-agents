import json
from collections import Counter
from pathlib import Path

p = Path("ui_evidence/data/reports/api-test/auth-user-apis-latest.json")
d = json.loads(p.read_text(encoding="utf-8"))
print("decision", d.get("decision"))
print("counts", d.get("counts"))
print("status", Counter(r.get("status") for r in d["results"]))
print("\nNON-PASS (excl SKIPPED):")
for r in d["results"]:
    if r.get("status") in {"FAILED", "SOFT_FAIL"}:
        print(
            f"  {r['status']:10} {r.get('http_status')} {r['service']} "
            f"{r['method']} {r['path']} err={r.get('error')}"
        )
print("\nSKIP reasons:")
print(Counter(r.get("reason") for r in d["results"] if r.get("status") == "SKIPPED"))
