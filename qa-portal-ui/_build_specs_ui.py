"""Build shell + tabs from extracted UI pieces."""
from __future__ import annotations

from pathlib import Path

ROOT = Path("lib/features/specs/presentation")
RAW = ROOT / "_extract_raw"
(ROOT / "shell").mkdir(exist_ok=True)
(ROOT / "tabs").mkdir(exist_ok=True)
(ROOT / "widgets").mkdir(exist_ok=True)

# --- qa_json_block ---
json_body = (RAW / "json.txt").read_text(encoding="utf-8")
json_body = json_body.replace("class _QaJsonBlock", "class QaJsonBlock")
json_body = json_body.replace("const _QaJsonBlock", "const QaJsonBlock")
(ROOT / "widgets" / "qa_json_block.dart").write_text(
    """import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import '../../domain/openapi_fill.dart';

"""
    + json_body
    + "\n",
    encoding="utf-8",
)

# --- import_pickers ---
imp = (RAW / "import.txt").read_text(encoding="utf-8")
imp = imp.replace("Future<void> _pickAndImport", "Future<void> pickAndImportPostman")
imp = imp.replace("_pickAndImport(", "pickAndImportPostman(")
(ROOT / "widgets" / "import_pickers.dart").write_text(
    """import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';

"""
    + imp
    + "\n",
    encoding="utf-8",
)

# --- data_tab ---
data = (RAW / "data.txt").read_text(encoding="utf-8")
data = data.replace("class _DataPane", "class SpecsDataTab")
data = data.replace("const _DataPane", "const SpecsDataTab")
data = data.replace("_QaJsonBlock", "QaJsonBlock")
data = data.replace("_pickAndImport", "pickAndImportPostman")
(ROOT / "tabs" / "data_tab.dart").write_text(
    """import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';
import '../widgets/import_pickers.dart';
import '../widgets/qa_json_block.dart';

"""
    + data
    + "\n",
    encoding="utf-8",
)

# --- usecases_tab ---
uc = (RAW / "usecases.txt").read_text(encoding="utf-8")
uc = uc.replace("class _UseCasesPane", "class SpecsUseCasesTab")
uc = uc.replace("const _UseCasesPane", "const SpecsUseCasesTab")
(ROOT / "tabs" / "usecases_tab.dart").write_text(
    """import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/network/json_lists.dart';
import '../../../../core/router/app_router.dart';
import '../../../services/presentation/widgets/coverage_board.dart';
import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';

"""
    + uc
    + "\n",
    encoding="utf-8",
)

# --- mcp_tab (temporary from extract; enhanced later) ---
mcp = (RAW / "mcp.txt").read_text(encoding="utf-8")
mcp = mcp.replace("class _McpPane", "class SpecsMcpTab")
mcp = mcp.replace("const _McpPane", "const SpecsMcpTab")
(ROOT / "tabs" / "mcp_tab.dart").write_text(
    """import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';

"""
    + mcp
    + "\n",
    encoding="utf-8",
)

# --- test_tab + swagger_tab (thin wrappers; wiring from shell) ---
(ROOT / "tabs" / "test_tab.dart").write_text(
    """import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';
import '../widgets/test_workspace.dart';

/// Test tab — Postman-like Try workspace.
class SpecsTestTab extends StatelessWidget {
  const SpecsTestTab({super.key});

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<SpecsCubit>();
    return BlocBuilder<SpecsCubit, SpecsState>(
      builder: (context, state) {
        final selectedVer = state.selectedPayloadVersion;
        return TestWorkspace(
          draft: state.draft,
          loading: state.loading,
          tryResult: state.tryResult,
          tryStatusCode: state.tryStatusCode,
          tryDurationMs: state.tryDurationMs,
          canRevert: state.canRevert,
          selectedPayloadVersion: selectedVer,
          targetUrl: state.targetUrl,
          paramEnums: state.paramEnums,
          onDraftChanged: cubit.updateDraft,
          onSend: () => cubit.testApiOneClick(),
          onMock: cubit.runTry,
          onFormat: cubit.formatBody,
          onBuild: () => cubit.buildPayload(),
          onEnsure: () => cubit.ensureWorking(),
          onRefreshPayload: cubit.refreshPayload,
          onRevert: cubit.revertDraft,
          onCopyCurl: () {
            Clipboard.setData(ClipboardData(text: cubit.copyCurlText()));
            final tgt = state.targetUrl ?? 'catalog target';
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('curl copied — $tgt')),
            );
          },
          onCopyResponse: () {
            if (state.tryResult == null) return;
            Clipboard.setData(ClipboardData(text: state.tryResult!));
          },
          onSaveSet: () => cubit.saveToCurrentSet(),
          onPickFile: cubit.pickFile,
          onRemoveFile: cubit.removeFile,
        );
      },
    );
  }
}
""",
    encoding="utf-8",
)

(ROOT / "tabs" / "swagger_tab.dart").write_text(
    """import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';
import '../widgets/swagger_embed.dart';

class SpecsSwaggerTab extends StatelessWidget {
  const SpecsSwaggerTab({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<SpecsCubit, SpecsState>(
      buildWhen: (p, c) =>
          p.openapiDoc != c.openapiDoc ||
          p.specRevision != c.specRevision ||
          p.loading != c.loading ||
          p.selectedService != c.selectedService,
      builder: (context, state) {
        if (state.openapiDoc == null) {
          return Center(
            child: Text(
              state.loading
                  ? 'Loading OpenAPI…'
                  : 'No OpenAPI document for ${state.selectedService ?? 'service'}.',
            ),
          );
        }
        return SwaggerEmbed(
          key: ValueKey(state.specRevision),
          document: state.openapiDoc!,
          specRevision: state.specRevision,
        );
      },
    );
  }
}
""",
    encoding="utf-8",
)

print("tabs + widgets written")
