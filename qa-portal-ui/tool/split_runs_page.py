from pathlib import Path

src = Path("lib/features/runs/presentation/pages/runs_page.dart")
lines = src.read_text(encoding="utf-8").splitlines(True)

col_start = None
for i, line in enumerate(lines):
    if line.startswith("  Widget _colHeader"):
        col_start = i
        break
if col_start is None:
    raise SystemExit("_colHeader not found")

# state class closes at first lone `}` after _colHeader
state_close = None
for i in range(col_start, len(lines)):
    if lines[i].rstrip() == "}":
        state_close = i
        break
if state_close is None:
    raise SystemExit("state close not found")

# main: everything before _colHeader, then close the state class
main_prefix = "".join(lines[:col_start]).rstrip() + "\n}\n"

# part: _colHeader as top-level (dedent 2 spaces) + rest after state_close
col_method = lines[col_start:state_close]  # excludes closing brace of state
dedented = []
for line in col_method:
    if line.startswith("  "):
        dedented.append(line[2:])
    else:
        dedented.append(line)
part_body = "".join(dedented) + "\n" + "".join(lines[state_close + 1 :])
while part_body.startswith("\n"):
    part_body = part_body[1:]
part = "part of 'runs_page.dart';\n\n" + part_body
if not part.endswith("\n"):
    part += "\n"

import_end = 0
for i, line in enumerate(lines):
    if line.startswith("import "):
        import_end = i + 1
    elif import_end and not line.startswith("import "):
        if line.strip() == "":
            import_end = i + 1
        break

head = "".join(lines[:import_end])
# main_prefix includes imports; strip duplicate imports
class_start = None
for i, line in enumerate(lines):
    if line.startswith("class RunsPage"):
        class_start = i
        break
# rebuild from class through before col_start, close state
rest = "".join(lines[class_start:col_start]).rstrip() + "\n}\n"
main_text = head + "\npart 'runs_page_cells.part.dart';\n\n" + rest
if not main_text.endswith("\n"):
    main_text += "\n"

src.write_text(main_text, encoding="utf-8")
(src.parent / "runs_page_cells.part.dart").write_text(part, encoding="utf-8")
print(f"main {main_text.count(chr(10))}  part {part.count(chr(10))}")
