"""Move all import/export directives above part directives."""
from pathlib import Path

files = [
    "lib/features/profiles/presentation/pages/profiles_page.dart",
    "lib/features/services/presentation/pages/services_page.dart",
    "lib/features/execute/presentation/pages/execute_bar.dart",
    "lib/features/services/presentation/widgets/coverage_board.dart",
    "lib/features/flows/presentation/widgets/credentials_manager.dart",
]

for path_s in files:
    path = Path(path_s)
    lines = path.read_text(encoding="utf-8").splitlines(True)
    imports: list[str] = []
    parts: list[str] = []
    other: list[str] = []
    for line in lines:
        if line.startswith("import ") or line.startswith("export "):
            imports.append(line)
        elif line.startswith("part "):
            parts.append(line)
        else:
            other.append(line)
    # drop leading blanks from other
    while other and other[0].strip() == "":
        other.pop(0)
    text = "".join(imports)
    if imports and not text.endswith("\n"):
        text += "\n"
    text += "\n" + "".join(parts) + "\n" + "".join(other)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")
    print("fixed", path)
