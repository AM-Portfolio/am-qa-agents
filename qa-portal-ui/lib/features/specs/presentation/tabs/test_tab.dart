import 'package:flutter/material.dart';
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
            final tgt = state.targetUrl ?? 'workspace target';
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
