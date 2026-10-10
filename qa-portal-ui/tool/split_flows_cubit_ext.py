"""Split FlowsCubit / UiFlowsCubit methods into same-library extensions via parts."""
from __future__ import annotations

import re
from pathlib import Path


def split_cubit(
    src: Path,
    *,
    class_name: str,
    field_end_line: int,
    close_start_line: int,
    parts: list[tuple[str, int, int]],
) -> None:
    """
    field_end_line: last line of fields/constructor inside class (1-based).
    close_start_line: start of close() method (1-based).
    parts: (filename, start, end) of method ranges to move into extensions.
    """
    lines = src.read_text(encoding="utf-8").splitlines(True)

    # imports through blank after imports
    import_end = 0
    seen = False
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("export "):
            seen = True
            import_end = i + 1
        elif seen and line.strip() == "":
            import_end = i + 1
            j = i + 1
            while j < len(lines) and (
                lines[j].startswith("import ")
                or lines[j].startswith("export ")
                or lines[j].strip() == ""
            ):
                if lines[j].startswith("import ") or lines[j].startswith("export "):
                    import_end = j + 1
                elif lines[j].strip() == "":
                    import_end = j + 1
                j += 1
            # continue to suck relative imports
            while j < len(lines) and (
                lines[j].startswith("import ") or lines[j].startswith("export ")
            ):
                import_end = j + 1
                j += 1
            while j < len(lines) and lines[j].strip() == "":
                import_end = j + 1
                j += 1
            break

    # Fix: re-scan all imports properly
    imports: list[str] = []
    rest_start = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("export ") or (
            line.startswith("final ") and "RegExp" in line
        ):
            imports.append(line)
            rest_start = i + 1
        elif line.strip() == "" and imports:
            # peek ahead
            if i + 1 < len(lines) and (
                lines[i + 1].startswith("import ")
                or lines[i + 1].startswith("export ")
                or (lines[i + 1].startswith("final ") and "RegExp" in lines[i + 1])
            ):
                continue
            rest_start = i + 1
            break
        elif imports:
            rest_start = i
            break

    close_body = "".join(lines[close_start_line - 1 :])
    # ensure close_body is just close() — strip trailing blanks
    # field block: from class line through field_end_line
    class_line = None
    for i, line in enumerate(lines):
        if line.startswith(f"class {class_name}"):
            class_line = i
            break
    if class_line is None:
        raise SystemExit(f"class {class_name} not found")

    fields = "".join(lines[class_line:field_end_line])
    # close method
    close_method = "".join(lines[close_start_line - 1 :]).rstrip() + "\n"

    part_dirs = "\n".join(f"part '{n}';" for n, _, _ in parts)
    main = "".join(imports)
    if not main.endswith("\n"):
        main += "\n"
    main += "\n" + part_dirs + "\n\n"
    main += fields.rstrip() + "\n\n"
    # indent close inside class
    main += close_method
    if not close_method.strip().startswith("@"):
        # close already has indent
        pass
    # If close_method doesn't end class, add closing brace
    if not main.rstrip().endswith("}"):
        main = main.rstrip() + "\n}\n"
    else:
        # close() ends with } for method; need class }
        # close method ends with `  }\n` — need one more `}\n` for class
        main = main.rstrip() + "\n}\n"

    src.write_text(main, encoding="utf-8")
    print(f"{main.count(chr(10)):4d} MAIN {src.name}")

    for name, a, b in parts:
        body = "".join(lines[a - 1 : b])
        # dedent method bodies from 2 spaces to 2 spaces still inside extension
        # methods already have 2-space indent; extension needs them at 2 spaces — OK
        # wrap in extension
        ext_name = name.replace(".part.dart", "").replace(".", "_")
        # rename private instance methods remain as methods on extension
        text = (
            f"part of '{src.name}';\n\n"
            f"extension {ext_name} on {class_name} {{\n"
            f"{body.rstrip()}\n"
            f"}}\n"
        )
        (src.parent / name).write_text(text, encoding="utf-8")
        print(f"{text.count(chr(10)):4d} {name} ({a}-{b})")


def main() -> None:
    # FlowsCubit: fields end line 15, methods 17-851, close at 852
    # Split methods into 3 parts under 600
    split_cubit(
        Path("lib/features/flows/presentation/cubit/flows_cubit.dart"),
        class_name="FlowsCubit",
        field_end_line=15,
        close_start_line=852,
        parts=[
            ("flows_cubit_load.part.dart", 17, 365),
            ("flows_cubit_runtime.part.dart", 366, 647),
            ("flows_cubit_draft.part.dart", 648, 851),
        ],
    )

    # UiFlowsCubit: fields through 20, load starts 22, close 688
    # _flowIdPattern is library-level before class
    split_cubit(
        Path("lib/features/ui_flows/presentation/cubit/ui_flows_cubit.dart"),
        class_name="UiFlowsCubit",
        field_end_line=20,
        close_start_line=688,
        parts=[
            ("ui_flows_cubit_edit.part.dart", 22, 363),
            ("ui_flows_cubit_run.part.dart", 364, 687),
        ],
    )


if __name__ == "__main__":
    main()
