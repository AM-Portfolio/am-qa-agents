from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("lib/features/specs/presentation")
RAW = ROOT / "_extract_raw"
(ROOT / "shell").mkdir(exist_ok=True)

view = (RAW / "view.txt").read_text(encoding="utf-8")
view = view.replace("class _SpecsView extends StatefulWidget", "class SpecsShell extends StatefulWidget")
view = view.replace("const _SpecsView()", "const SpecsShell({super.key})")
view = view.replace("State<_SpecsView>", "State<SpecsShell>")
view = view.replace("createState() => _SpecsViewState()", "createState() => _SpecsShellState()")
view = view.replace(
    "class _SpecsViewState extends State<_SpecsView>",
    "class _SpecsShellState extends State<SpecsShell>",
)
view = view.replace(
    "class _SpecsViewState extends State<SpecsShell>",
    "class _SpecsShellState extends State<SpecsShell>",
)

pattern = r"child: TabBarView\(\s*controller: _tabs,\s*children: \[.*?\],\s*\),"
replacement = """child: TabBarView(
                                    controller: _tabs,
                                    children: [
                                      const SpecsTestTab(),
                                      const SpecsSwaggerTab(),
                                      SpecsMcpTab(state: state),
                                      SpecsUseCasesTab(state: state),
                                      SpecsDataTab(state: state),
                                    ],
                                  ),"""
view, n = re.subn(pattern, replacement, view, count=1, flags=re.S)
print("tabview replacements", n)
if n != 1:
    raise SystemExit("failed to rewrite TabBarView")

# method colors
mc = ""
m = re.search(
    r"  Color _methodBg\(String m\) \{.*?\n  \}\n\n  Color _methodFg\(String m\) \{.*?\n  \}\n",
    view,
    re.S,
)
if m:
    mc = m.group(0)
    mc = mc.replace("Color _methodBg", "Color methodBg").replace("Color _methodFg", "Color methodFg")
    view = view[: m.start()] + view[m.end() :]
    view = view.replace("_methodBg(", "methodBg(").replace("_methodFg(", "methodFg(")

(ROOT / "shell" / "method_colors.dart").write_text(
    "import 'package:am_design_system/am_design_system.dart';\n"
    "import 'package:flutter/material.dart';\n\n"
    + mc
    + "\n",
    encoding="utf-8",
)

# Extract catalog rail (GlassCard with Catalog) and api rail as separate widgets later;
# keep inline in shell for compile correctness, provide thin public wrappers.
(ROOT / "shell" / "catalog_rail.dart").write_text(
    "/// Catalog rail UI is composed inside [SpecsShell]; file marks ownership.\n"
    "library;\n",
    encoding="utf-8",
)
(ROOT / "shell" / "api_rail.dart").write_text(
    "/// API rail UI is composed inside [SpecsShell]; file marks ownership.\n"
    "library;\n",
    encoding="utf-8",
)

header = """import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/config/portal_config.dart';
import '../../../../core/di/injection.dart';
import '../../domain/openapi_fill.dart';
import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';
import '../tabs/data_tab.dart';
import '../tabs/mcp_tab.dart';
import '../tabs/swagger_tab.dart';
import '../tabs/test_tab.dart';
import '../tabs/usecases_tab.dart';
import 'method_colors.dart';

"""

(ROOT / "shell" / "specs_shell.dart").write_text(header + view + "\n", encoding="utf-8")
print("shell lines", len(view.splitlines()))
