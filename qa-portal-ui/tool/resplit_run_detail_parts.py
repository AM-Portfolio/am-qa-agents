from pathlib import Path

dir_ = Path("lib/features/runs/presentation/pages")


def split_part(src_name: str, cuts: list[tuple[str, int, int | None]]) -> None:
    """cuts: (out_name, start_1based_inclusive, end_1based_inclusive_or_None)."""
    src = dir_ / src_name
    lines = src.read_text(encoding="utf-8").splitlines(True)
    # drop existing part of header from first file content when re-slicing body
    body_start = 0
    if lines and lines[0].startswith("part of"):
        body_start = 1
        if body_start < len(lines) and lines[body_start].strip() == "":
            body_start += 1
    body = lines[body_start:]
    for name, a, b in cuts:
        # a/b relative to body as 1-based within body
        chunk = body[a - 1 : (b if b is not None else None)]
        text = "part of 'run_detail_page.dart';\n\n" + "".join(chunk)
        if not text.endswith("\n"):
            text += "\n"
        (dir_ / name).write_text(text, encoding="utf-8")
        print(f"{text.count(chr(10)):4d} {name}")


# summary body: Overview 1-447, Baseline+ 448-end (1-based in body after header)
# After part header, class _OverviewTab is line 1 of body = file line 3
# Baseline starts at body line 448 (file 450 - 2 header lines)
split_part(
    "run_detail_summary.part.dart",
    [
        ("run_detail_summary.part.dart", 1, 447),
        ("run_detail_baseline.part.dart", 448, None),
    ],
)

# inspector: Inspector through end of State = body lines 1-316
# TraceDetailPanel starts body line 317
split_part(
    "run_detail_inspector.part.dart",
    [
        ("run_detail_inspector.part.dart", 1, 316),
        ("run_detail_trace_panel.part.dart", 317, None),
    ],
)

# update main part list
main = dir_ / "run_detail_page.dart"
text = main.read_text(encoding="utf-8")
old = """part 'run_detail_cubit.part.dart';
part 'run_detail_view.part.dart';
part 'run_detail_helpers.part.dart';
part 'run_detail_summary.part.dart';
part 'run_detail_trace_utils.part.dart';
part 'run_detail_inspector.part.dart';
part 'run_detail_tabs.part.dart';"""
new = """part 'run_detail_cubit.part.dart';
part 'run_detail_view.part.dart';
part 'run_detail_helpers.part.dart';
part 'run_detail_summary.part.dart';
part 'run_detail_baseline.part.dart';
part 'run_detail_trace_utils.part.dart';
part 'run_detail_inspector.part.dart';
part 'run_detail_trace_panel.part.dart';
part 'run_detail_tabs.part.dart';"""
if old not in text:
    raise SystemExit("part block not found in main")
main.write_text(text.replace(old, new), encoding="utf-8")
print("updated run_detail_page.dart parts")
