import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../data/execute_repository.dart';

class ExecuteBar extends StatelessWidget {
  const ExecuteBar({
    super.key,
    this.apiOk = false,
    this.apiMessage,
    this.onClearCache,
  });

  final bool apiOk;
  final String? apiMessage;
  final VoidCallback? onClearCache;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => _ExecuteCubit(getIt<ExecuteRepository>())..boot(),
      child: _ExecuteBarView(
        apiOk: apiOk,
        apiMessage: apiMessage,
        onClearCache: onClearCache,
      ),
    );
  }
}

class _ExecuteState {
  const _ExecuteState({
    this.configs = const [],
    this.flowIds = const [],
    this.suiteIds = const [],
    this.catalogApis = const [],
    this.selectedApiIds = const {},
    this.openapiVersions = const [],
    this.configId,
    this.testType = 'k6',
    this.vus = 1,
    this.calls = 1,
    this.runProfile = 'debug',
    this.reportFormats = const ['html', 'json'],
    this.openapiVersion,
    this.preset = 'custom',
    this.uiProfile,
    this.uiSuite,
    this.lastRunId,
    this.busy = false,
    this.message,
  });

  final List<Map<String, dynamic>> configs;
  final List<String> flowIds;
  final List<String> suiteIds;
  final List<Map<String, dynamic>> catalogApis;
  final Set<String> selectedApiIds;
  final List<String> openapiVersions;
  final String? configId;
  final String testType;
  final int vus;
  final int calls;
  final String runProfile;
  final List<String> reportFormats;
  final String? openapiVersion;
  final String preset;
  final String? uiProfile;
  final String? uiSuite;
  final String? lastRunId;
  final bool busy;
  final String? message;

  Map<String, dynamic>? get selectedConfig {
    for (final c in configs) {
      if ('${c['id']}' == configId) return c;
    }
    return null;
  }

  String get audience => '${selectedConfig?['audience'] ?? 'developer'}';

  bool get audienceLocked => audience != 'developer' && audience.isNotEmpty;

  _ExecuteState copyWith({
    List<Map<String, dynamic>>? configs,
    List<String>? flowIds,
    List<String>? suiteIds,
    List<Map<String, dynamic>>? catalogApis,
    Set<String>? selectedApiIds,
    List<String>? openapiVersions,
    String? configId,
    String? testType,
    int? vus,
    int? calls,
    String? runProfile,
    List<String>? reportFormats,
    String? openapiVersion,
    String? preset,
    String? uiProfile,
    String? uiSuite,
    String? lastRunId,
    bool? busy,
    String? message,
    bool clearUiProfile = false,
    bool clearUiSuite = false,
    bool clearLastRun = false,
    bool clearOpenapiVersion = false,
  }) {
    return _ExecuteState(
      configs: configs ?? this.configs,
      flowIds: flowIds ?? this.flowIds,
      suiteIds: suiteIds ?? this.suiteIds,
      catalogApis: catalogApis ?? this.catalogApis,
      selectedApiIds: selectedApiIds ?? this.selectedApiIds,
      openapiVersions: openapiVersions ?? this.openapiVersions,
      configId: configId ?? this.configId,
      testType: testType ?? this.testType,
      vus: vus ?? this.vus,
      calls: calls ?? this.calls,
      runProfile: runProfile ?? this.runProfile,
      reportFormats: reportFormats ?? this.reportFormats,
      openapiVersion:
          clearOpenapiVersion ? null : (openapiVersion ?? this.openapiVersion),
      preset: preset ?? this.preset,
      uiProfile: clearUiProfile ? null : (uiProfile ?? this.uiProfile),
      uiSuite: clearUiSuite ? null : (uiSuite ?? this.uiSuite),
      lastRunId: clearLastRun ? null : (lastRunId ?? this.lastRunId),
      busy: busy ?? this.busy,
      message: message,
    );
  }
}

class _ExecuteCubit extends Cubit<_ExecuteState> {
  _ExecuteCubit(this._repo) : super(const _ExecuteState());

  final ExecuteRepository _repo;

  Future<void> boot() async {
    try {
      final configs = await _repo.listConfigs();
      final ui = await _repo.uiCatalog();
      final flows = <String>[];
      for (final key in ['flows', 'deterministic', 'release_gate']) {
        final list = ui[key];
        if (list is List) {
          for (final f in list) {
            if (f is Map && f['id'] != null) flows.add('${f['id']}');
            if (f is String) flows.add(f);
          }
        }
      }
      final suites = <String>[];
      final raw = ui['suites'];
      if (raw is List) {
        for (final s in raw) {
          if (s is Map && s['id'] != null) suites.add('${s['id']}');
          if (s is String) suites.add(s);
        }
      }
      emit(
        state.copyWith(
          configs: configs,
          flowIds: flows.toSet().toList()..sort(),
          suiteIds: suites.toSet().toList()..sort(),
          configId: configs.isEmpty ? null : '${configs.first['id'] ?? ''}',
        ),
      );
      await _syncFromConfig(state.configId);
    } catch (e) {
      emit(state.copyWith(message: e.toString()));
    }
  }

  Future<void> selectConfig(String? id) async {
    emit(state.copyWith(configId: id));
    await _syncFromConfig(id);
  }

  Future<void> _syncFromConfig(String? id) async {
    if (id == null) return;
    final cfg = state.selectedConfig;
    if (cfg == null) return;
    final tt = '${cfg['test_type'] ?? state.testType}';
    final vus = cfg['vus'];
    final iters = cfg['iterations'] ?? cfg['calls'];
    final audience = '${cfg['audience'] ?? 'developer'}';
    final locked = audience != 'developer' && audience.isNotEmpty;
    final selected = <String>{};
    final ids = cfg['selected_api_ids'] ?? cfg['api_ids'];
    if (ids is List) {
      for (final x in ids) {
        selected.add('$x');
      }
    }
    emit(
      state.copyWith(
        testType: tt.isEmpty ? state.testType : tt,
        vus: locked ? 1 : (vus is int ? vus : (int.tryParse('$vus') ?? state.vus)),
        calls: locked
            ? 1
            : (iters is int ? iters : (int.tryParse('$iters') ?? state.calls)),
        uiProfile: cfg['ui_profile']?.toString(),
        uiSuite: cfg['ui_suite']?.toString(),
        openapiVersion: cfg['openapi_version']?.toString(),
        selectedApiIds: selected,
        clearUiProfile: cfg['ui_profile'] == null,
        clearUiSuite: cfg['ui_suite'] == null,
      ),
    );
    final service = '${cfg['service'] ?? ''}';
    final env = '${cfg['environment'] ?? 'dev'}';
    if (service.isNotEmpty) {
      try {
        final apis = await _repo.serviceApis(service, environment: env);
        final versions = await _repo.openapiVersions(service);
        emit(state.copyWith(catalogApis: apis, openapiVersions: versions));
      } catch (_) {}
    }
  }

  void applyPreset(String preset) {
    if (state.audienceLocked) {
      emit(state.copyWith(preset: preset, vus: 1, calls: 1, message: 'Audience locked to 1×1'));
      return;
    }
    switch (preset) {
      case 'smoke':
        emit(state.copyWith(preset: preset, vus: 1, calls: 5, runProfile: 'debug'));
        break;
      case 'load':
        emit(state.copyWith(preset: preset, vus: 10, calls: 50, runProfile: 'load'));
        break;
      case '20u-50':
        emit(state.copyWith(preset: preset, vus: 20, calls: 50, runProfile: 'load'));
        break;
      case 'stress':
        emit(state.copyWith(preset: preset, vus: 50, calls: 200, runProfile: 'load'));
        break;
      default:
        emit(state.copyWith(preset: 'custom'));
    }
  }

  void setTestType(String t) => emit(state.copyWith(testType: t));
  void setVus(int v) {
    if (state.audienceLocked) return;
    emit(state.copyWith(vus: v, preset: 'custom'));
  }

  void setCalls(int c) {
    if (state.audienceLocked) return;
    emit(state.copyWith(calls: c, preset: 'custom'));
  }

  void setRunProfile(String p) {
    if (p == 'debug') {
      emit(state.copyWith(runProfile: p, vus: 1, calls: 1, preset: 'custom'));
    } else {
      emit(state.copyWith(runProfile: p));
    }
  }

  void setReportFormats(List<String> f) => emit(state.copyWith(reportFormats: f));
  void setOpenapiVersion(String? v) =>
      emit(state.copyWith(openapiVersion: v, clearOpenapiVersion: v == null));
  void setUiProfile(String? v) =>
      emit(state.copyWith(uiProfile: v, clearUiProfile: v == null));
  void setUiSuite(String? v) =>
      emit(state.copyWith(uiSuite: v, clearUiSuite: v == null));
  void setSelectedApis(Set<String> ids) => emit(state.copyWith(selectedApiIds: ids));

  Future<String?> run({String? service, String? environment}) async {
    final id = state.configId;
    if (id == null || id.isEmpty) {
      emit(state.copyWith(message: 'Select a profile'));
      return null;
    }
    final cfg = state.selectedConfig;
    final svc = (service ?? '${cfg?['service'] ?? ''}').trim();
    final env = (environment ?? '${cfg?['environment'] ?? ''}').trim();
    emit(state.copyWith(busy: true, message: null));
    try {
      final out = await _repo.execute(
        configId: id,
        // Bind OpenAPI catalog service when template profiles have empty service.
        service: svc.isEmpty ? null : svc,
        environment: env.isEmpty ? null : env,
        testType: state.testType,
        vus: state.vus,
        calls: state.calls,
        profile: state.runProfile,
        uiProfile: state.uiProfile,
        uiSuite: state.uiSuite,
        reportFormats: state.reportFormats,
        // Empty selection = all OpenAPI APIs for the bound service.
        apiIds: state.selectedApiIds.isEmpty ? null : state.selectedApiIds.toList(),
        openapiVersion: state.openapiVersion,
      );
      final runId = '${out['id'] ?? out['run_id'] ?? ''}';
      emit(state.copyWith(busy: false, message: 'Started', lastRunId: runId));
      return runId;
    } catch (e) {
      emit(state.copyWith(busy: false, message: e.toString()));
      return null;
    }
  }

  Future<void> stopLast() async {
    final id = state.lastRunId;
    if (id == null || id.isEmpty) {
      emit(state.copyWith(message: 'No active run from this bar'));
      return;
    }
    try {
      await _repo.stopRun(id);
      emit(state.copyWith(message: 'Stop requested', clearLastRun: true));
    } catch (e) {
      emit(state.copyWith(message: e.toString()));
    }
  }
}

class _ExecuteBarView extends StatelessWidget {
  const _ExecuteBarView({
    required this.apiOk,
    this.apiMessage,
    this.onClearCache,
  });

  final bool apiOk;
  final String? apiMessage;
  final VoidCallback? onClearCache;

  Future<void> _pickApis(BuildContext context) async {
    final cubit = context.read<_ExecuteCubit>();
    final state = cubit.state;
    if (state.catalogApis.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No APIs for this profile service')),
      );
      return;
    }
    final selected = Set<String>.from(state.selectedApiIds);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setLocal) {
            return AlertDialog(
              title: Text('Pick APIs (${selected.length}/${state.catalogApis.length})'),
              content: SizedBox(
                width: 520,
                height: 420,
                child: Column(
                  children: [
                    Row(
                      children: [
                        TextButton(
                          onPressed: () => setLocal(() {
                            selected
                              ..clear()
                              ..addAll(
                                state.catalogApis.map(
                                  (a) => '${a['id'] ?? a['operationId'] ?? ''}',
                                ).where((e) => e.isNotEmpty),
                              );
                          }),
                          child: const Text('Select all'),
                        ),
                        TextButton(
                          onPressed: () => setLocal(selected.clear),
                          child: const Text('Clear'),
                        ),
                      ],
                    ),
                    Expanded(
                      child: ListView.builder(
                        itemCount: state.catalogApis.length,
                        itemBuilder: (_, i) {
                          final a = state.catalogApis[i];
                          final id = '${a['id'] ?? a['operationId'] ?? i}';
                          final method = '${a['method'] ?? ''}'.toUpperCase();
                          final path = '${a['path'] ?? a['url'] ?? ''}';
                          return CheckboxListTile(
                            dense: true,
                            value: selected.contains(id),
                            title: Text('$method $path'),
                            subtitle: Text(id),
                            onChanged: (v) => setLocal(() {
                              if (v == true) {
                                selected.add(id);
                              } else {
                                selected.remove(id);
                              }
                            }),
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Apply')),
              ],
            );
          },
        );
      },
    );
    if (ok == true) cubit.setSelectedApis(selected);
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 6),
        child: GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          child: BlocBuilder<_ExecuteCubit, _ExecuteState>(
            builder: (context, state) {
              final needsUi =
                  state.testType == 'playwright' || state.testType == 'mixed';
              final cfg = state.selectedConfig;
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Text(
                        'Execute',
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                              color: AppColors.primary,
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                      const SizedBox(width: 8),
                      Chip(
                        visualDensity: VisualDensity.compact,
                        avatar: Icon(
                          Icons.favorite,
                          size: 12,
                          color: apiOk
                              ? Colors.green
                              : Theme.of(context).colorScheme.error,
                        ),
                        label: Text(
                          apiOk ? 'api ok' : (apiMessage ?? 'api down'),
                          style: const TextStyle(fontSize: 11),
                        ),
                      ),
                      const Spacer(),
                      if (onClearCache != null)
                        TextButton.icon(
                          onPressed: onClearCache,
                          icon: const Icon(Icons.cleaning_services, size: 16),
                          label: const Text('Clear cache'),
                        ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      _dd(
                        width: 220,
                        label: 'Config',
                        value: state.configId,
                        items: [
                          for (final c in state.configs)
                            DropdownMenuItem(
                              value: '${c['id']}',
                              child: Text(
                                _configLabel(c),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                        ],
                        onChanged: state.busy
                            ? null
                            : (v) =>
                                context.read<_ExecuteCubit>().selectConfig(v),
                      ),
                      _dd(
                        width: 110,
                        label: 'Preset',
                        value: state.preset,
                        items: const [
                          DropdownMenuItem(value: 'custom', child: Text('custom')),
                          DropdownMenuItem(value: 'smoke', child: Text('smoke 1×1')),
                          DropdownMenuItem(value: 'load', child: Text('load 20×50')),
                          DropdownMenuItem(value: '20u-50', child: Text('20u×50')),
                          DropdownMenuItem(value: 'stress', child: Text('stress')),
                        ],
                        onChanged: state.busy
                            ? null
                            : (v) {
                                if (v != null) {
                                  context.read<_ExecuteCubit>().applyPreset(v);
                                }
                              },
                      ),
                      _dd(
                        width: 120,
                        label: 'Runner',
                        value: state.testType,
                        items: const [
                          DropdownMenuItem(value: 'k6', child: Text('API (k6)')),
                          DropdownMenuItem(
                            value: 'playwright',
                            child: Text('UI (PW)'),
                          ),
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
                      _dd(
                        width: 100,
                        label: 'Intensity',
                        value: state.runProfile,
                        items: const [
                          DropdownMenuItem(value: 'debug', child: Text('1-call')),
                          DropdownMenuItem(value: 'load', child: Text('load')),
                        ],
                        onChanged: state.busy
                            ? null
                            : (v) {
                                if (v != null) {
                                  context.read<_ExecuteCubit>().setRunProfile(v);
                                }
                              },
                      ),
                      SizedBox(
                        width: 72,
                        child: TextFormField(
                          key: ValueKey('vus-${state.vus}'),
                          initialValue: '${state.vus}',
                          enabled: !state.audienceLocked && !state.busy,
                          decoration: const InputDecoration(
                            labelText: 'VUs',
                            isDense: true,
                            border: OutlineInputBorder(),
                          ),
                          keyboardType: TextInputType.number,
                          onChanged: (v) {
                            final n = int.tryParse(v);
                            if (n != null) {
                              context.read<_ExecuteCubit>().setVus(n);
                            }
                          },
                        ),
                      ),
                      SizedBox(
                        width: 80,
                        child: TextFormField(
                          key: ValueKey('calls-${state.calls}'),
                          initialValue: '${state.calls}',
                          enabled: !state.audienceLocked && !state.busy,
                          decoration: const InputDecoration(
                            labelText: 'Calls',
                            isDense: true,
                            border: OutlineInputBorder(),
                          ),
                          keyboardType: TextInputType.number,
                          onChanged: (v) {
                            final n = int.tryParse(v);
                            if (n != null) {
                              context.read<_ExecuteCubit>().setCalls(n);
                            }
                          },
                        ),
                      ),
                      if (state.testType != 'playwright')
                        OutlinedButton(
                          onPressed: state.busy ? null : () => _pickApis(context),
                          child: Text(
                            state.selectedApiIds.isEmpty
                                ? 'APIs: all'
                                : 'APIs: ${state.selectedApiIds.length}',
                          ),
                        ),
                      if (needsUi) ...[
                        _dd(
                          width: 150,
                          label: 'UI flow',
                          value: state.uiProfile,
                          items: [
                            const DropdownMenuItem(
                              value: null,
                              child: Text('(none)'),
                            ),
                            for (final id in state.flowIds)
                              DropdownMenuItem(
                                value: id,
                                child: Text(id, overflow: TextOverflow.ellipsis),
                              ),
                          ],
                          onChanged: state.busy
                              ? null
                              : (v) => context
                                  .read<_ExecuteCubit>()
                                  .setUiProfile(v),
                        ),
                        _dd(
                          width: 120,
                          label: 'UI suite',
                          value: state.uiSuite,
                          items: [
                            const DropdownMenuItem(
                              value: null,
                              child: Text('(none)'),
                            ),
                            for (final id in state.suiteIds)
                              DropdownMenuItem(value: id, child: Text(id)),
                            const DropdownMenuItem(
                              value: 'smoke',
                              child: Text('smoke'),
                            ),
                            const DropdownMenuItem(
                              value: 'release_gate',
                              child: Text('release_gate'),
                            ),
                          ],
                          onChanged: state.busy
                              ? null
                              : (v) =>
                                  context.read<_ExecuteCubit>().setUiSuite(v),
                        ),
                      ],
                      FilledButton.icon(
                        onPressed: state.busy
                            ? null
                            : () async {
                                // Prefer service from /services/:id or /specs?spec=
                                final loc = GoRouterState.of(context).uri;
                                String? routeService;
                                final path = loc.path;
                                final m = RegExp(r'^/services/([^/]+)').firstMatch(path);
                                if (m != null) {
                                  routeService = Uri.decodeComponent(m.group(1)!);
                                } else {
                                  final spec = loc.queryParameters['spec'];
                                  if (spec != null && spec.isNotEmpty) {
                                    routeService = spec;
                                  }
                                }
                                final env = loc.queryParameters['env'];
                                final id = await context.read<_ExecuteCubit>().run(
                                      service: routeService,
                                      environment: env,
                                    );
                                if (id != null &&
                                    id.isNotEmpty &&
                                    context.mounted) {
                                  context.go('/runs/$id');
                                }
                              },
                        icon: state.busy
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.play_arrow, size: 18),
                        label: const Text('Run'),
                      ),
                      if (state.lastRunId != null)
                        OutlinedButton.icon(
                          onPressed: state.busy
                              ? null
                              : () => context.read<_ExecuteCubit>().stopLast(),
                          icon: const Icon(Icons.stop, size: 16),
                          label: const Text('Stop'),
                        ),
                      if (state.audienceLocked)
                        Chip(
                          label: Text('${state.audience} → 1×1'),
                          visualDensity: VisualDensity.compact,
                        ),
                      if (cfg != null)
                        Text(
                          '${cfg['service'] ?? ''}/${cfg['environment'] ?? ''}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      if (state.message != null)
                        Text(
                          state.message!,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                    ],
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  static String _configLabel(Map<String, dynamic> c) {
    final name = '${c['name'] ?? c['id'] ?? ''}'.replaceAll(RegExp(r'-+$'), '');
    final svc = '${c['service'] ?? ''}'.trim();
    final env = '${c['environment'] ?? ''}'.trim();
    if (svc.isEmpty) return name;
    return env.isEmpty ? '$name · $svc' : '$name · $svc/$env';
  }

  Widget _dd({
    required double width,
    required String label,
    required String? value,
    required List<DropdownMenuItem<String?>> items,
    required ValueChanged<String?>? onChanged,
  }) {
    return SizedBox(
      width: width,
      child: DropdownButtonFormField<String?>(
        key: ValueKey('$label-$value'),
        initialValue: value,
        isExpanded: true,
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          border: const OutlineInputBorder(),
          contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        ),
        items: items,
        onChanged: onChanged,
      ),
    );
  }
}
