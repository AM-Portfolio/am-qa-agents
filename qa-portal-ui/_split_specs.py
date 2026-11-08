from pathlib import Path

src = Path(r"lib/features/specs/presentation/pages/specs_page.dart")
lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
base = Path(r"lib/features/specs/presentation")
for d in ("cubit", "shell", "tabs", "_extract_raw"):
    (base / d).mkdir(parents=True, exist_ok=True)

chunks = {
    "state": (41, 287),
    "cubit": (289, 1493),
    "view": (1497, 2170),
    "mcp": (2172, 2382),
    "usecases": (2384, 2453),
    "import": (2455, 2531),
    "data": (2533, 2774),
    "json": (2776, 2824),
}
raw = base / "_extract_raw"
for k, (a, b) in chunks.items():
    text = "".join(lines[a - 1 : b])
    (raw / f"{k}.txt").write_text(text, encoding="utf-8")
    print(k, len(text.splitlines()))
print("done")
