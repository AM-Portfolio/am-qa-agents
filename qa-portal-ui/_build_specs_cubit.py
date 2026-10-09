"""Build specs_state + specs_cubit under presentation/cubit/."""
from __future__ import annotations

from pathlib import Path

ROOT = Path("lib/features/specs/presentation")
RAW = ROOT / "_extract_raw"
CUBIT_DIR = ROOT / "cubit"
CUBIT_DIR.mkdir(parents=True, exist_ok=True)

state_body = (RAW / "state.txt").read_text(encoding="utf-8")
if "mcpToolReport" not in state_body:
    state_body = state_body.replace(
        "    this.mcpTools = const [],\n",
        "    this.mcpTools = const [],\n"
        "    this.mcpToolReport,\n"
        "    this.mcpRunning = false,\n"
        "    this.selectedMcpToolNames = const {},\n",
    )
    state_body = state_body.replace(
        "  final List<Map<String, dynamic>> mcpTools;\n",
        "  final List<Map<String, dynamic>> mcpTools;\n"
        "  final Map<String, dynamic>? mcpToolReport;\n"
        "  final bool mcpRunning;\n"
        "  final Set<String> selectedMcpToolNames;\n",
    )
    state_body = state_body.replace(
        "    List<Map<String, dynamic>>? mcpTools,\n",
        "    List<Map<String, dynamic>>? mcpTools,\n"
        "    Map<String, dynamic>? mcpToolReport,\n"
        "    bool? mcpRunning,\n"
        "    Set<String>? selectedMcpToolNames,\n",
    )
    state_body = state_body.replace(
        "    bool clearMcpSummary = false,\n",
        "    bool clearMcpSummary = false,\n"
        "    bool clearMcpReport = false,\n",
    )
    state_body = state_body.replace(
        "      mcpSummary: clearMcpSummary ? null : (mcpSummary ?? this.mcpSummary),\n"
        "      mcpTools: clearMcpTools ? const [] : (mcpTools ?? this.mcpTools),\n",
        "      mcpSummary: clearMcpSummary ? null : (mcpSummary ?? this.mcpSummary),\n"
        "      mcpTools: clearMcpTools ? const [] : (mcpTools ?? this.mcpTools),\n"
        "      mcpToolReport: clearMcpReport ? null : (mcpToolReport ?? this.mcpToolReport),\n"
        "      mcpRunning: mcpRunning ?? this.mcpRunning,\n"
        "      selectedMcpToolNames:\n"
        "          selectedMcpToolNames ?? this.selectedMcpToolNames,\n",
    )
    state_body = state_body.replace(
        "        mcpTools,\n",
        "        mcpTools,\n"
        "        mcpToolReport,\n"
        "        mcpRunning,\n"
        "        selectedMcpToolNames,\n",
    )

(CUBIT_DIR / "specs_state.dart").write_text(
    "import 'package:equatable/equatable.dart';\n\n"
    "import '../../domain/openapi_fill.dart';\n"
    "import '../../domain/try_draft.dart';\n\n"
    + state_body
    + "\n",
    encoding="utf-8",
)

cubit = (RAW / "cubit.txt").read_text(encoding="utf-8")
cubit = cubit.replace(
    "class SpecsCubit extends Cubit<SpecsState> {\n"
    "  SpecsCubit(this._repo, this._executeRepo, this._dio) : super(const SpecsState());\n\n"
    "  final SpecsRepository _repo;\n"
    "  final ExecuteRepository _executeRepo;\n"
    "  final Dio _dio;\n"
    "  final TryHistory _history = TryHistory();\n",
    "class SpecsCubit extends Cubit<SpecsState>\n"
    "    with\n"
    "        SpecsCubitCatalogMixin,\n"
    "        SpecsCubitTestMixin,\n"
    "        SpecsCubitDataMixin,\n"
    "        SpecsCubitUseCasesMixin,\n"
    "        SpecsCubitMcpMixin {\n"
    "  SpecsCubit(this.repo, this.executeRepo, this.dio) : super(const SpecsState());\n\n"
    "  final SpecsRepository repo;\n"
    "  final ExecuteRepository executeRepo;\n"
    "  final Dio dio;\n"
    "  final TryHistory history = TryHistory();\n",
)
for a, b in [
    ("_repo", "repo"),
    ("_executeRepo", "executeRepo"),
    ("_dio", "dio"),
    ("_history", "history"),
]:
    cubit = cubit.replace(a, b)

header = """import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/json_lists.dart';
import '../../../execute/data/execute_repository.dart';
import '../../data/specs_repository.dart';
import '../../domain/openapi_fill.dart';
import '../../domain/try_draft.dart';
import 'specs_cubit_catalog.mixin.dart';
import 'specs_cubit_data.mixin.dart';
import 'specs_cubit_mcp.mixin.dart';
import 'specs_cubit_test.mixin.dart';
import 'specs_cubit_usecases.mixin.dart';
import 'specs_state.dart';

export 'specs_state.dart';

"""

(CUBIT_DIR / "specs_cubit.dart").write_text(header + cubit + "\n", encoding="utf-8")

mixin_src = """import 'package:flutter_bloc/flutter_bloc.dart';

import 'specs_state.dart';

/// Boundary mixin — method implementations live on [SpecsCubit] unless noted.
mixin %s on Cubit<SpecsState> {}
"""
for fname, mname in [
    ("specs_cubit_catalog.mixin.dart", "SpecsCubitCatalogMixin"),
    ("specs_cubit_test.mixin.dart", "SpecsCubitTestMixin"),
    ("specs_cubit_data.mixin.dart", "SpecsCubitDataMixin"),
    ("specs_cubit_usecases.mixin.dart", "SpecsCubitUseCasesMixin"),
]:
    (CUBIT_DIR / fname).write_text(mixin_src % mname, encoding="utf-8")

# MCP mixin starts empty; run-tool methods appended later by hand/script
(CUBIT_DIR / "specs_cubit_mcp.mixin.dart").write_text(
    mixin_src % "SpecsCubitMcpMixin",
    encoding="utf-8",
)

print("ok", (CUBIT_DIR / "specs_cubit.dart").stat().st_size)
