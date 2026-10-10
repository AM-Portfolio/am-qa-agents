"""Move FlowNodeComposeCardState methods (except build) into an extension part."""
from pathlib import Path

src = Path("lib/features/flows/presentation/widgets/flow_node_compose_card.dart")
lines = src.read_text(encoding="utf-8").splitlines(True)

# Find method block: first Future/void after fields, until build(
method_start = None
build_start = None
payload_start = None
for i, line in enumerate(lines):
    if method_start is None and (
        line.startswith("  Future<void> _bootstrap")
        or line.startswith("  Future<void> _")
    ):
        method_start = i
    if line.startswith("  Widget build("):
        build_start = i
    if line.startswith("class _PayloadOpt"):
        payload_start = i

if method_start is None or build_start is None or payload_start is None:
    raise SystemExit(f"markers missing {method_start} {build_start} {payload_start}")

# State class closes just before _PayloadOpt — find `}` before payload
state_close = None
for i in range(payload_start - 1, -1, -1):
    if lines[i].strip() == "}":
        state_close = i
        break

imports: list[str] = []
i = 0
while i < len(lines):
    if lines[i].startswith("import "):
        imports.append(lines[i])
        i += 1
        continue
    if lines[i].strip() == "" and imports:
        if i + 1 < len(lines) and lines[i + 1].startswith("import "):
            i += 1
            continue
        i += 1
        break
    break

# prefix: enums + widget + state through before methods
prefix = "".join(lines[i:method_start])
methods = "".join(lines[method_start:build_start])
build_and_close = "".join(lines[build_start : state_close + 1])
payload = "".join(lines[payload_start:])

main = (
    "".join(imports)
    + "\npart 'flow_node_compose_methods.part.dart';\n"
    + "part 'flow_node_compose_payload.part.dart';\n\n"
    + prefix.lstrip("\n")
    + build_and_close
)
if not main.endswith("\n"):
    main += "\n"

methods_part = (
    "part of 'flow_node_compose_card.dart';\n\n"
    "extension FlowNodeComposeMethods on _FlowNodeComposeCardState {\n"
    f"{methods.rstrip()}\n"
    "}\n"
)
payload_part = "part of 'flow_node_compose_card.dart';\n\n" + payload
if not payload_part.endswith("\n"):
    payload_part += "\n"

src.write_text(main, encoding="utf-8")
(src.parent / "flow_node_compose_methods.part.dart").write_text(
    methods_part, encoding="utf-8"
)
(src.parent / "flow_node_compose_payload.part.dart").write_text(
    payload_part, encoding="utf-8"
)
print(f"main {main.count(chr(10))} methods {methods_part.count(chr(10))} payload {payload_part.count(chr(10))}")
