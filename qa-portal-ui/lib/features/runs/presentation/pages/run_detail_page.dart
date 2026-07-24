import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../../../core/router/app_router.dart';
import '../../data/runs_repository.dart';

class RunDetailPage extends StatelessWidget {
  const RunDetailPage({super.key, required this.runId});

  final String runId;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => _RunDetailCubit(getIt<RunsRepository>(), runId)..load(),
      child: _RunDetailView(runId: runId),
    );
  }
}

class _RunDetailState {
  const _RunDetailState({
    this.loading = true,
    this.run = const {},
    this.error,
  });

  final bool loading;
  final Map<String, dynamic> run;
  final String? error;

  _RunDetailState copyWith({
    bool? loading,
    Map<String, dynamic>? run,
    String? error,
  }) {
    return _RunDetailState(
      loading: loading ?? this.loading,
      run: run ?? this.run,
      error: error,
    );
  }
}

class _RunDetailCubit extends Cubit<_RunDetailState> {
  _RunDetailCubit(this._repo, this.runId) : super(const _RunDetailState());

  final RunsRepository _repo;
  final String runId;

  Future<void> load() async {
    emit(state.copyWith(loading: true, error: null));
    try {
      final run = await _repo.getRun(runId);
      emit(state.copyWith(loading: false, run: run));
      final status = '${run['status'] ?? ''}';
      if (status == 'running' || status == 'pending') {
        Future<void>.delayed(const Duration(seconds: 2), () {
          if (!isClosed) load();
        });
      }
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }

  Future<void> stop() async {
    try {
      await _repo.stopRun(runId);
      await load();
    } catch (e) {
      emit(state.copyWith(error: e.toString()));
    }
  }
}

class _RunDetailView extends StatelessWidget {
  const _RunDetailView({required this.runId});

  final String runId;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: BlocBuilder<_RunDetailCubit, _RunDetailState>(
        builder: (context, state) {
          if (state.loading && state.run.isEmpty) {
            return const Center(child: CircularProgressIndicator());
          }
          if (state.error != null && state.run.isEmpty) {
            return Center(child: Text(state.error!));
          }
          final run = state.run;
          final status = '${run['status'] ?? ''}';
          final pretty = const JsonEncoder.withIndent('  ').convert(run);
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  IconButton(
                    onPressed: () => context.go(AppRoutes.runs),
                    icon: const Icon(Icons.arrow_back),
                  ),
                  Expanded(
                    child: Text(
                      'Run $runId',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                  ),
                  if (status == 'running' || status == 'pending')
                    FilledButton.tonalIcon(
                      onPressed: () => context.read<_RunDetailCubit>().stop(),
                      icon: const Icon(Icons.stop),
                      label: const Text('Stop'),
                    ),
                  const SizedBox(width: 8),
                  OutlinedButton.icon(
                    onPressed: () => context.read<_RunDetailCubit>().load(),
                    icon: const Icon(Icons.refresh, size: 18),
                    label: const Text('Refresh'),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text('Status: $status'),
              Text('Type: ${run['test_type'] ?? ''}'),
              Text('Config: ${run['config_name'] ?? run['config_id'] ?? ''}'),
              if (run['error'] != null) ...[
                const SizedBox(height: 8),
                Text(
                  '${run['error']}',
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 16),
              Expanded(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: SingleChildScrollView(
                      child: SelectableText(
                        pretty,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
