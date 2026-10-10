import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/di/injection.dart';
import '../../data/runs_repository.dart';
import '../../../specs/data/specs_repository.dart';
import '../../../specs/presentation/widgets/test_workspace.dart';
import '../cubit/run_api_try_cubit.dart';

bool _isNetworkNoise(String text) {
  final lower = text.toLowerCase();
  return lower.contains('dioexception') ||
      lower.contains('xmlhttprequest') ||
      lower.contains('cors') ||
      lower.contains('connection errored') ||
      lower.contains('could not load working payload');
}

String _shortBanner(String text) {
  final t = text.trim();
  if (t.isEmpty) return t;
  if (_isNetworkNoise(t)) {
    return 'Working payload unavailable — fill params and Send';
  }
  if (t.length <= 120) return t;
  return '${t.substring(0, 117)}…';
}

/// Embeds Specs [TestWorkspace] for fixing a failed run API against its payload set.
class RunApiTryPanel extends StatelessWidget {
  const RunApiTryPanel({
    super.key,
    required this.run,
    required this.row,
    this.onClose,
  });

  final Map<String, dynamic> run;
  final Map<String, dynamic> row;
  final VoidCallback? onClose;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => RunApiTryCubit(
            getIt<SpecsRepository>(),
            getIt<Dio>(),
            getIt<RunsRepository>(),
          )..openFor(run: run, row: row),
      child: _RunApiTryBody(onClose: onClose),
    );
  }
}

class _RunApiTryBody extends StatelessWidget {
  const _RunApiTryBody({this.onClose});

  final VoidCallback? onClose;

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<RunApiTryCubit, RunApiTryState>(
      builder: (context, state) {
        final cubit = context.read<RunApiTryCubit>();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Test · ${state.draft.method} · '
                    'dataset ${state.payloadSetVersion == null ? '—' : 'v${state.payloadSetVersion}'}',
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
                if (onClose != null)
                  IconButton(
                    tooltip: 'Close try',
                    visualDensity: VisualDensity.compact,
                    onPressed: onClose,
                    icon: const Icon(Icons.close, size: 18),
                  ),
              ],
            ),
            if (state.runFailure != null && state.runFailure!.isNotEmpty) ...[
              const SizedBox(height: 2),
              Text(
                _shortBanner(state.runFailure!),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Theme.of(context).colorScheme.error,
                    ),
              ),
            ],
            if (state.message != null &&
                state.message!.isNotEmpty &&
                !_isNetworkNoise(state.message!)) ...[
              const SizedBox(height: 2),
              Text(
                _shortBanner(state.message!),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ],
            Expanded(
              child: TestWorkspace(
                draft: state.draft,
                loading: state.loading,
                tryResult: state.tryResult,
                tryStatusCode: state.tryStatusCode,
                tryDurationMs: state.tryDurationMs,
                canRevert: state.canRevert,
                selectedPayloadVersion: state.payloadSetVersion,
                targetUrl: state.targetUrl,
                paramEnums: state.paramEnums,
                onDraftChanged: cubit.updateDraft,
                onSend: cubit.runTry,
                onFormat: cubit.formatBody,
                onBuild: cubit.buildPayload,
                onEnsure: cubit.ensureWorking,
                onRefreshPayload: cubit.refreshPayload,
                onRevert: cubit.revertDraft,
                onCopyCurl: () {
                  Clipboard.setData(ClipboardData(text: cubit.copyCurlText()));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('curl copied')),
                  );
                },
                onCopyResponse: () {
                  if (state.tryResult == null) return;
                  Clipboard.setData(ClipboardData(text: state.tryResult!));
                },
                onSaveSet: cubit.saveToCurrentSet,
                onPickFile: cubit.pickFile,
                onRemoveFile: cubit.removeFile,
              ),
            ),
          ],
        );
      },
    );
  }
}
