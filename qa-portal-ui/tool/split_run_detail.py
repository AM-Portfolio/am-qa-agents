from pathlib import Path

src = Path("lib/features/runs/presentation/pages/run_detail_page.dart")
lines = src.read_text(encoding="utf-8").splitlines(True)


def chunk(a: int, b: int) -> str:
    return "".join(lines[a - 1 : b])


parts = {
    "run_detail_cubit.part.dart": (32, 287),
    "run_detail_view.part.dart": (288, 685),
    "run_detail_helpers.part.dart": (687, 763),
    "run_detail_summary.part.dart": (765, 1387),
    "run_detail_trace_utils.part.dart": (1388, 1565),
    "run_detail_inspector.part.dart": (1566, 2243),
    "run_detail_tabs.part.dart": (2244, 2387),
}

out_dir = src.parent
for name, (a, b) in parts.items():
    body = chunk(a, b)
    text = "part of 'run_detail_page.dart';\n\n" + body
    if not text.endswith("\n"):
        text += "\n"
    (out_dir / name).write_text(text, encoding="utf-8")
    print(f"{text.count(chr(10)):4d} {name} ({a}-{b})")

import_block = "".join(lines[0:16])
page_block = chunk(18, 30)
part_dirs = "\n".join(f"part '{n}';" for n in parts)
main = import_block + "\n" + part_dirs + "\n\n" + page_block
if not main.endswith("\n"):
    main += "\n"
src.write_text(main, encoding="utf-8")
print(f"{main.count(chr(10)):4d} run_detail_page.dart (main)")
