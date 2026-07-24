import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../data/execute_repository.dart';

class ExecuteBar extends StatelessWidget {
  const ExecuteBar({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => _ExecuteCubit(getIt<ExecuteRepository>())..loadConfigs(),
      child: const _ExecuteBarView(),
    );
  }
}

class _ExecuteState {
  const _ExecuteState({
    this.configs = const [],
    this.configId,
    this.testType = 'k6',
    this.vus = 1,
    this.calls = 1,
    this.busy = false,
    this.message,
  });

  final List<Map<String, dynamic>> configs;
  final String? configId;
  final String testType;
  final int vus;
  final int calls;
  final bool busy;
  final String? message;

  _ExecuteState copyWith({
    List<Map<String, dynamic>>? configs,
    String? configId,
    String? testType,
    int? vus,
    int? calls,
    bool? busy,
    String? message,
  }) {
    return _ExecuteState(
      configs: configs ?? this.configs,
      configId: configId ?? this.configId,
      testType: testType ?? this.testType,
      vus: vus ?? this.vus,
      calls: calls ?? this.calls,
      busy: busy ?? this.busy,
      message: message,
    );
  }
}

class _ExecuteCubit extends Cubit<_ExecuteState> {
  _ExecuteCubit(this._repo) : super(const _ExecuteState());

  final ExecuteRepository _repo;

  Future<void> loadConfigs() async {
    try {
      final configs = await _repo.listConfigs();
      emit(
        state.copyWith(
          configs: configs,
          configId: configs.isEmpty
              ? null
              : '${configs.first['id'] ?? ''}',
        ),
      );
    } catch (e) {
      emit(state.copyWith(message: e.toString()));
    }
  }

  void selectConfig(String? id) => emit(state.copyWith(configId: id));

  void setTestType(String t) => emit(state.copyWith(testType: t));

  Future<String?> run() async {
    final id = state.configId;
    if (id == null || id.isEmpty) {
      emit(state.copyWith(message: 'Select a profile'));
      return null;
    }
    emit(state.copyWith(busy: true, message: null));
    try {
      final out = await _repo.execute(
        configId: id,
        testType: state.testType,
        vus: state.vus,
        calls: state.calls,
      );
      emit(state.copyWith(busy: false, message: 'Started'));
      return '${out['id'] ?? out['run_id'] ?? ''}';
    } catch (e) {
      emit(state.copyWith(busy: false, message: e.toString()));
      return null;
    }
  }
}

class _ExecuteBarView extends StatelessWidget {
  const _ExecuteBarView();

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.35),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: BlocBuilder<_ExecuteCubit, _ExecuteState>(
          builder: (context, state) {
            return Wrap(
              spacing: 12,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Text(
                  'Execute',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w700,
                      ),
                ),
                SizedBox(
                  width: 220,
                  child: DropdownButtonFormField<String>(
                    key: ValueKey('cfg-${state.configId}'),
                    initialValue: state.configId?.isEmpty == true ? null : state.configId,
                    decoration: const InputDecoration(
                      labelText: 'Profile',
                      isDense: true,
                      border: OutlineInputBorder(),
                    ),
                    items: [
                      for (final c in state.configs)
                        DropdownMenuItem(
                          value: '${c['id']}',
                          child: Text('${c['name'] ?? c['id']}'),
                        ),
                    ],
                    onChanged: state.busy
                        ? null
                        : (v) => context.read<_ExecuteCubit>().selectConfig(v),
                  ),
                ),
                SizedBox(
                  width: 140,
                  child: DropdownButtonFormField<String>(
                    key: ValueKey('type-${state.testType}'),
                    initialValue: state.testType,
                    decoration: const InputDecoration(
                      labelText: 'Type',
                      isDense: true,
                      border: OutlineInputBorder(),
                    ),
                    items: const [
                      DropdownMenuItem(value: 'k6', child: Text('k6')),
                      DropdownMenuItem(value: 'playwright', child: Text('Playwright')),
                      DropdownMenuItem(value: 'mixed', child: Text('Mixed')),
                    ],
                    onChanged: state.busy
                        ? null
                        : (v) {
                            if (v != null) {
                              context.read<_ExecuteCubit>().setTestType(v);
                            }
                          },
                  ),
                ),
                FilledButton.icon(
                  onPressed: state.busy
                      ? null
                      : () async {
                          final id = await context.read<_ExecuteCubit>().run();
                          if (id != null && id.isNotEmpty && context.mounted) {
                            context.go('/runs/$id');
                          }
                        },
                  icon: state.busy
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.play_arrow),
                  label: const Text('Run test'),
                ),
                if (state.message != null)
                  Text(
                    state.message!,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}
