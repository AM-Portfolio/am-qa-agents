"""Split Cubit methods into same-library extensions via part files."""
from __future__ import annotations

from pathlib import Path


def split_cubit(
    src: Path,
    class_name: str,
    field_end_line: int,
    close_start_line: int,
    parts: list[tuple[str, int, int]],
) -> None:
    lines = src.read_text(encoding="utf-8").splitlines(True)

    imports: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if (
            line.startswith("import ")
            or line.startswith("export ")
            or (line.startswith("final ") and "RegExp" in line)
        ):
            imports.append(line)
            i += 1
            continue
        if line.strip() == "" and imports:
            if i + 1 < len(lines) and (
                lines[i + 1].startswith("import ")
                or lines[i + 1].startswith("export ")
                or (lines[i + 1].startswith("final ") and "RegExp" in lines[i + 1])
            ):
                i += 1
                continue
            i += 1
            break
        break

    class_line = None
    for j, line in enumerate(lines):
        if line.startswith(f"class {class_name}"):
            class_line = j
            break
    if class_line is None:
        raise SystemExit(f"class {class_name} not found")

    fields = "".join(lines[class_line:field_end_line])

    brace_lines = [j for j, l in enumerate(lines) if l.strip() == "}"]
    method_close = brace_lines[-2]
    close_method = "".join(lines[close_start_line - 1 : method_close + 1])

    part_dirs = "\n".join(f"part '{n}';" for n, _, _ in parts)
    main = "".join(imports) + "\n" + part_dirs + "\n\n"
    main += fields.rstrip() + "\n\n" + close_method.rstrip() + "\n}\n"
    src.write_text(main, encoding="utf-8")
    print(f"{main.count(chr(10)):4d} MAIN {src.name}")

    for name, a, b in parts:
        body = "".join(lines[a - 1 : b])
        ext = name.replace(".part.dart", "").replace(".", "_").replace("-", "_")
        ext_name = "".join(p.title() for p in ext.split("_"))
        text = (
            f"part of '{src.name}';\n\n"
            f"extension {ext_name} on {class_name} {{\n"
            f"{body.rstrip()}\n"
            f"}}\n"
        )
        (src.parent / name).write_text(text, encoding="utf-8")
        print(f"{text.count(chr(10)):4d} {name}")


def main() -> None:
    root = Path("lib/features")
    flows_bak = root / "flows/presentation/cubit/flows_cubit.dart.bak"
    ui_bak = root / "ui_flows/presentation/cubit/ui_flows_cubit.dart.bak"
    if flows_bak.exists():
        (root / "flows/presentation/cubit/flows_cubit.dart").write_text(
            flows_bak.read_text(encoding="utf-8"), encoding="utf-8"
        )
    if ui_bak.exists():
        (root / "ui_flows/presentation/cubit/ui_flows_cubit.dart").write_text(
            ui_bak.read_text(encoding="utf-8"), encoding="utf-8"
        )

    split_cubit(
        root / "flows/presentation/cubit/flows_cubit.dart",
        "FlowsCubit",
        15,
        851,
        [
            ("flows_cubit_load.part.dart", 17, 365),
            ("flows_cubit_runtime.part.dart", 366, 647),
            ("flows_cubit_draft.part.dart", 648, 850),
        ],
    )
    split_cubit(
        root / "ui_flows/presentation/cubit/ui_flows_cubit.dart",
        "UiFlowsCubit",
        20,
        687,
        [
            ("ui_flows_cubit_edit.part.dart", 22, 363),
            ("ui_flows_cubit_run.part.dart", 364, 686),
        ],
    )


if __name__ == "__main__":
    main()
