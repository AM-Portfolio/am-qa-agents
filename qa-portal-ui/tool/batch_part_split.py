"""Split multi-class Dart files into part files (≤600 lines each)."""
from __future__ import annotations

from pathlib import Path


def write_part(path: Path, body: str) -> int:
    text = f"part of '{path.name.replace('.part.dart', '').split('_')[0]}'\n"
    # caller passes correct part-of name
    raise NotImplementedError


def split_file(
    src: Path,
    *,
    main_end_line: int,
    parts: list[tuple[str, int, int]],
    part_of: str | None = None,
) -> None:
    """
    main keeps lines 1..main_end_line (inclusive) plus part directives after imports.
    parts: (filename, start, end) 1-based inclusive line ranges from original.
    """
    lines = src.read_text(encoding="utf-8").splitlines(True)
    part_of_name = part_of or src.name

    # find end of import block (last import or blank after imports)
    import_end = 0
    seen_import = False
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("export "):
            seen_import = True
            import_end = i + 1
        elif seen_import and line.strip() == "":
            import_end = i + 1
            # keep consuming blank lines, stop at first non-import non-blank
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                import_end = j + 1
                j += 1
            break
        elif seen_import and not line.startswith("import ") and not line.startswith("export "):
            break

    head = "".join(lines[:import_end])
    main_body = "".join(lines[import_end:main_end_line])
    # if main_body starts with blank lines after we already have blanks in head, ok

    part_dirs = "\n".join(f"part '{name}';" for name, _, _ in parts)
    main = head
    if not main.endswith("\n"):
        main += "\n"
    main += "\n" + part_dirs + "\n\n" + main_body.lstrip("\n")
    if not main.endswith("\n"):
        main += "\n"
    src.write_text(main, encoding="utf-8")
    print(f"{main.count(chr(10)):4d} {src}")

    for name, a, b in parts:
        body = "".join(lines[a - 1 : b])
        text = f"part of '{part_of_name}';\n\n" + body
        if not text.endswith("\n"):
            text += "\n"
        out = src.parent / name
        out.write_text(text, encoding="utf-8")
        print(f"{text.count(chr(10)):4d} {out.name} ({a}-{b})")


def main() -> None:
    root = Path("lib/features")

    # profiles_page: page 15-30, then rest as parts
    split_file(
        root / "profiles/presentation/pages/profiles_page.dart",
        main_end_line=30,
        parts=[
            ("profiles_state_cubit.part.dart", 31, 252),
            ("profiles_view.part.dart", 253, 755),
            ("profiles_hover.part.dart", 756, 9999),
        ],
    )

    # services_page
    split_file(
        root / "services/presentation/pages/services_page.dart",
        main_end_line=28,
        parts=[
            ("services_state_cubit.part.dart", 29, 209),
            ("services_view.part.dart", 210, 339),
            ("services_overview.part.dart", 340, 9999),
        ],
    )

    # execute_bar
    split_file(
        root / "execute/presentation/pages/execute_bar.dart",
        main_end_line=33,
        parts=[
            ("execute_state_cubit.part.dart", 34, 328),
            ("execute_bar_view.part.dart", 329, 9999),
        ],
    )

    # coverage_board — keep CoverageBoard + State in main through line 366
    split_file(
        root / "services/presentation/widgets/coverage_board.dart",
        main_end_line=366,
        parts=[
            ("coverage_suite.part.dart", 367, 560),
            ("coverage_case.part.dart", 561, 9999),
        ],
    )

    # credentials_manager: keep showCredentialsManager + dialog class header in main
    # Dialog state is huge — split state class body is impossible; split sibling classes.
    split_file(
        root / "flows/presentation/widgets/credentials_manager.dart",
        main_end_line=515,
        parts=[
            ("credentials_status.part.dart", 516, 576),
            ("credentials_add_picker.part.dart", 577, 9999),
        ],
    )

    # flow_node_compose_card: keep card+state, extract _PayloadOpt + trailing helpers if any
    # State alone is ~660 lines — need deeper extract. Skip here; handled separately.
    print("done batch")


if __name__ == "__main__":
    main()
