import 'dart:convert';

import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/config/portal_config.dart';
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
    this.actionBusy = false,
    this.run = const {},
    this.artifacts = const [],
    this.apis = const [],
    this.traces = const [],
    this.selectedTrace,
    this.selectedTraceApiId,
    this.failedOnly = false,
    this.baseline,
    this.error,
  });

  final bool loading;
  final bool actionBusy;
  final Map<String, dynamic> run;
  final List<Map<String, dynamic>> artifacts;
  final List<Map<String, dynamic>> apis;
  final List<Map<String, dynamic>> traces;
  final Map<String, dynamic>? selectedTrace;
  final String? selectedTraceApiId;
  final bool failedOnly;
  final Map<String, dynamic>? baseline;
  final String? error;

  _RunDetailState copyWith({
    bool? loading,
    bool? actionBusy,
    Map<String, dynamic>? run,
    List<Map<String, dynamic>>? artifacts,
    List<Map<String, dynamic>>? apis,
    List<Map<String, dynamic>>? traces,
    Map<String, dynamic>? selectedTrace,
    String? selectedTraceApiId,
    bool? failedOnly,
    Map<String, dynamic>? baseline,
    String? error,
    bool clearTrace = false,
    bool clearTraceApiId = false,
  }) {
    return _RunDetailState(
      loading: loading ?? this.loading,
      actionBusy: actionBusy ?? this.actionBusy,
      run: run ?? this.run,
      artifacts: artifacts ?? this.artifacts,
      apis: apis ?? this.apis,
      traces: traces ?? this.traces,
      selectedTrace: clearTrace ? null : (selectedTrace ?? this.selectedTrace),
      selectedTraceApiId:
          clearTraceApiId ? null : (selectedTraceApiId ?? this.selectedTraceApiId),
      failedOnly: failedOnly ?? this.failedOnly,
      baseline: baseline ?? this.baseline,
      error: error,
    );
  }
}

int _intFrom(dynamic v, int fallback) {
  if (v is int) return v;
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? fallback;
  return fallback;
}

Map<String, dynamic> _runParams(Map<String, dynamic> run) {
  final params = run['params'];
  return params is Map ? Map<String, dynamic>.from(params) : const {};
}

String? _runIdFrom(Map<String, dynamic> out) {
  final id = '${out['id'] ?? out['run_id'] ?? ''}';
  return id.isEmpty ? null : id;
}

class _RunDetailCubit extends Cubit<_RunDetailState> {
  _RunDetailCubit(this._repo, this.runId) : super(const _RunDetailState());

  final RunsRepository _repo;
  final String runId;

  Future<void> load() async {
    emit(state.copyWith(loading: true, error: null));
    try {
      final run = await _repo.getRun(runId);
      List<Map<String, dynamic>> arts = const [];
      List<Map<String, dynamic>> apis = const [];
      List<Map<String, dynamic>> traces = const [];
      Map<String, dynamic>? baseline;
      try {
        arts = await _repo.artifacts(runId);
      } catch (_) {}
      try {
        apis = await _repo.runApis(runId, failedOnly: state.failedOnly);
      } catch (_) {}
      try {
        traces = await _repo.traces(runId, failedOnly: state.failedOnly);
      } catch (_) {}
      try {
        baseline = await _repo.baseline(runId);
      } catch (_) {}
      emit(
        state.copyWith(
          loading: false,
          run: run,
          artifacts: arts,
          apis: apis,
          traces: traces,
          baseline: baseline,
        ),
      );
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

  Future<void> setFailedOnly(bool v) async {
    emit(state.copyWith(failedOnly: v));
    await load();
  }

  Future<void> openTrace(Map<String, dynamic> row) async {
    final apiId = '${row['api_id'] ?? row['id'] ?? ''}';
    final index = row['index'];
    try {
      Map<String, dynamic> detail;
      if (index is int) {
        detail = await _repo.traceAt(runId, index);
      } else if (apiId.isNotEmpty) {
        detail = await _repo.apiTrace(runId, apiId);
      } else {
        detail = row;
      }
      final trace = detail['trace'] is Map
          ? Map<String, dynamic>.from(detail['trace'] as Map)
          : detail;
      final traceApiId = '${trace['api_id'] ?? apiId}';
      emit(
        state.copyWith(
          selectedTrace: trace,
          selectedTraceApiId: traceApiId.isEmpty ? null : traceApiId,
        ),
      );
    } catch (e) {
      emit(state.copyWith(error: e.toString()));
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

  Future<String?> rerun() async {
    final run = state.run;
    final configId = '${run['config_id'] ?? ''}';
    if (configId.isEmpty) {
      emit(state.copyWith(error: 'Run has no config_id'));
      return null;
    }
    final params = _runParams(run);
    final testType = '${run['test_type'] ?? 'k6'}';
    final vus = _intFrom(params['vus'] ?? run['vus'], 1);
    final calls = _intFrom(params['iterations'] ?? params['calls'] ?? run['iterations'], 1);
    emit(state.copyWith(actionBusy: true, error: null));
    try {
      final out = await _repo.execute(
        configId: configId,
        testType: testType,
        vus: vus,
        calls: calls,
        profile: 'load',
      );
      emit(state.copyWith(actionBusy: false));
      return _runIdFrom(out);
    } catch (e) {
      emit(state.copyWith(actionBusy: false, error: e.toString()));
      return null;
    }
  }

  Future<String?> debugRun() async {
    final run = state.run;
    final configId = '${run['config_id'] ?? ''}';
    if (configId.isEmpty) {
      emit(state.copyWith(error: 'Run has no config_id'));
      return null;
    }
    final testType = '${run['test_type'] ?? 'k6'}';
    emit(state.copyWith(actionBusy: true, error: null));
    try {
      final out = await _repo.execute(
        configId: configId,
        testType: testType,
        vus: 1,
        calls: 1,
        profile: 'debug',
      );
      emit(state.copyWith(actionBusy: false));
      return _runIdFrom(out);
    } catch (e) {
      emit(state.copyWith(actionBusy: false, error: e.toString()));
      return null;
    }
  }

  Future<Map<String, dynamic>?> saveAsConfig(String name) async {
    emit(state.copyWith(actionBusy: true, error: null));
    try {
      final out = await _repo.saveAsConfig(runId, name: name);
      emit(state.copyWith(actionBusy: false));
      return out;
    } catch (e) {
      emit(state.copyWith(actionBusy: false, error: e.toString()));
      return null;
    }
  }

  Future<Map<String, dynamic>?> exportRun() async {
    emit(state.copyWith(actionBusy: true, error: null));
    try {
      final out = await _repo.exportRun(runId);
      emit(state.copyWith(actionBusy: false));
      return out;
    } catch (e) {
      emit(state.copyWith(actionBusy: false, error: e.toString()));
      return null;
    }
  }

  Future<Map<String, dynamic>?> savePayload(String apiId, {String? name}) async {
    emit(state.copyWith(actionBusy: true, error: null));
    try {
      final out = await _repo.savePayload(runId, apiId, name: name);
      emit(state.copyWith(actionBusy: false));
      return out;
    } catch (e) {
      emit(state.copyWith(actionBusy: false, error: e.toString()));
      return null;
    }
  }
}

class _RunDetailView extends StatelessWidget {
  const _RunDetailView({required this.runId});

  final String runId;

  String _absUrl(PortalConfig cfg, String url) {
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    var path = url.startsWith('/') ? url : '/$url';
    final base = cfg.apiBase.replaceAll(RegExp(r'/$'), '');
    // Avoid /spt-poc + /spt-poc/api/... when server stored ROOT_PATH-prefixed paths
    final basePath = Uri.tryParse(base)?.path ?? '';
    if (basePath.isNotEmpty && basePath != '/' && path.startsWith(basePath)) {
      path = path.substring(basePath.length);
      if (!path.startsWith('/')) path = '/$path';
    }
    return '$base$path';
  }

  Future<void> _saveAsConfigDialog(BuildContext context) async {
    final nameCtrl = TextEditingController(text: 'from-run-${runId.substring(0, 8)}');
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Save as config'),
        content: SizedBox(
          width: 360,
          child: TextField(
            controller: nameCtrl,
            decoration: const InputDecoration(
              labelText: 'Config name',
              border: OutlineInputBorder(),
            ),
            autofocus: true,
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    final name = nameCtrl.text.trim();
    if (name.isEmpty) return;
    final out = await context.read<_RunDetailCubit>().saveAsConfig(name);
    if (!context.mounted) return;
    if (out != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Saved config ${out['name'] ?? out['id'] ?? name}')),
      );
    }
  }

  Future<void> _exportJsonDialog(BuildContext context) async {
    final data = await context.read<_RunDetailCubit>().exportRun();
    if (!context.mounted || data == null) return;
    final pretty = const JsonEncoder.withIndent('  ').convert(data);
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Export run JSON'),
        content: SizedBox(
          width: 640,
          height: 480,
          child: SingleChildScrollView(
            child: SelectableText(
              pretty,
              style: Theme.of(ctx).textTheme.bodySmall,
            ),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
        ],
      ),
    );
  }

  Future<void> _startRunAndGo(
    BuildContext context,
    Future<String?> Function() start,
  ) async {
    final newId = await start();
    if (!context.mounted || newId == null) return;
    context.go('/runs/$newId');
  }

  Future<void> _savePayloadDialog(BuildContext context, String apiId) async {
    final nameCtrl = TextEditingController(text: 'default');
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Save payload'),
        content: SizedBox(
          width: 360,
          child: TextField(
            controller: nameCtrl,
            decoration: const InputDecoration(
              labelText: 'Payload name',
              border: OutlineInputBorder(),
            ),
            autofocus: true,
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    final name = nameCtrl.text.trim();
    final out = await context.read<_RunDetailCubit>().savePayload(
          apiId,
          name: name.isEmpty ? null : name,
        );
    if (!context.mounted) return;
    if (out != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Saved ${out['name'] ?? 'payload'} v${out['version'] ?? ''}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final cfg = getIt<PortalConfig>();
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
          final live = run['live'];
          final liveMap = live is Map ? Map<String, dynamic>.from(live) : null;
          final grafana = '${run['grafana_url'] ?? ''}';
          final metrics = run['metrics'] is Map
              ? Map<String, dynamic>.from(run['metrics'] as Map)
              : null;
          final results = run['results'];
          final isLive = status == 'running' || status == 'pending';
          final cubit = context.read<_RunDetailCubit>();

          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Column(
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
                          'Run ${runId.length > 8 ? runId.substring(0, 8) : runId}',
                          style: Theme.of(context).textTheme.headlineSmall,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      IconButton(
                        tooltip: 'Copy run id',
                        visualDensity: VisualDensity.compact,
                        icon: const Icon(Icons.copy, size: 18),
                        onPressed: () async {
                          await Clipboard.setData(ClipboardData(text: runId));
                          if (!context.mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Run id copied'),
                              duration: Duration(seconds: 1),
                            ),
                          );
                        },
                      ),
                      if (state.actionBusy)
                        const Padding(
                          padding: EdgeInsets.only(left: 4, right: 8),
                          child: SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        ),
                    ],
                  ),
                  Padding(
                    padding: const EdgeInsets.only(left: 48),
                    child: SelectableText(
                      runId,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            fontFamily: 'monospace',
                          ),
                      maxLines: 1,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      if (grafana.isNotEmpty)
                        OutlinedButton.icon(
                          onPressed: state.actionBusy
                              ? null
                              : () => launchUrl(Uri.parse(grafana)),
                          icon: const Icon(Icons.insights, size: 18),
                          label: const Text('Grafana'),
                        ),
                      if (isLive)
                        FilledButton.tonalIcon(
                          onPressed: state.actionBusy ? null : () => cubit.stop(),
                          icon: const Icon(Icons.stop),
                          label: const Text('Stop'),
                        )
                      else ...[
                        OutlinedButton.icon(
                          onPressed: state.actionBusy
                              ? null
                              : () => _startRunAndGo(context, cubit.rerun),
                          icon: const Icon(Icons.replay, size: 18),
                          label: const Text('Re-run'),
                        ),
                        OutlinedButton.icon(
                          onPressed: state.actionBusy
                              ? null
                              : () => _startRunAndGo(context, cubit.debugRun),
                          icon: const Icon(Icons.bug_report, size: 18),
                          label: const Text('Debug 1-call'),
                        ),
                      ],
                      OutlinedButton.icon(
                        onPressed:
                            state.actionBusy ? null : () => _saveAsConfigDialog(context),
                        icon: const Icon(Icons.save_as, size: 18),
                        label: const Text('Save as config'),
                      ),
                      OutlinedButton.icon(
                        onPressed:
                            state.actionBusy ? null : () => _exportJsonDialog(context),
                        icon: const Icon(Icons.code, size: 18),
                        label: const Text('Export JSON'),
                      ),
                      OutlinedButton.icon(
                        onPressed: state.actionBusy ? null : () => cubit.load(),
                        icon: const Icon(Icons.refresh, size: 18),
                        label: const Text('Refresh'),
                      ),
                    ],
                  ),
                ],
              ),
              if (state.error != null && state.run.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  state.error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Chip(
                    label: Text(status.isEmpty ? 'unknown' : status),
                    backgroundColor: AppColors.primary.withValues(alpha: 0.12),
                  ),
                  Text(
                    '${run['test_type'] ?? ''} · '
                    '${run['config_name'] ?? run['config_id'] ?? ''} · '
                    '${run['service'] ?? ''}/${run['environment'] ?? ''}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (run['passed'] == true)
                    const Chip(label: Text('passed'), avatar: Icon(Icons.check, size: 16)),
                  if (run['passed'] == false && status != 'running')
                    Chip(
                      label: const Text('failed'),
                      avatar: Icon(Icons.close, size: 16, color: Theme.of(context).colorScheme.error),
                    ),
                  if (run['api_count'] != null ||
                      run['api_pass_count'] != null ||
                      run['api_fail_count'] != null)
                    Chip(
                      label: Text(
                        'APIs ${run['api_count'] ?? '—'} · '
                        '${run['api_pass_count'] ?? '—'}✓ / ${run['api_fail_count'] ?? '—'}✗',
                      ),
                    ),
                ],
              ),
              if (liveMap != null) ...[
                const SizedBox(height: 8),
                LinearProgressIndicator(
                  value: liveMap['pct'] is num
                      ? (liveMap['pct'] as num).toDouble().clamp(0, 100) / 100
                      : null,
                ),
                const SizedBox(height: 4),
                Text(
                  '${liveMap['phase'] ?? ''} — ${liveMap['message'] ?? ''}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
              if (metrics != null && metrics.isNotEmpty) ...[
                const SizedBox(height: 8),
                Wrap(
                  spacing: 12,
                  children: [
                    for (final e in metrics.entries.take(8))
                      Chip(
                        label: Text('${e.key}: ${e.value}'),
                        visualDensity: VisualDensity.compact,
                      ),
                  ],
                ),
              ],
              const SizedBox(height: 12),
              Expanded(
                child: DefaultTabController(
                  length: 4,
                  child: Column(
                    children: [
                      const TabBar(
                        isScrollable: true,
                        tabs: [
                          Tab(text: 'Overview'),
                          Tab(text: 'Inspector'),
                          Tab(text: 'Artifacts'),
                          Tab(text: 'APIs'),
                        ],
                      ),
                      Expanded(
                        child: TabBarView(
                          children: [
                            _OverviewTab(
                              run: run,
                              results: results,
                              baseline: state.baseline,
                              apis: state.apis,
                              absUrl: (u) => _absUrl(cfg, u),
                            ),
                            _InspectorTab(
                              traces: state.traces.isEmpty ? state.apis : state.traces,
                              selected: state.selectedTrace,
                              selectedApiId: state.selectedTraceApiId,
                              failedOnly: state.failedOnly,
                              onFailedOnly: cubit.setFailedOnly,
                              onOpen: cubit.openTrace,
                              onSavePayload: (apiId) => _savePayloadDialog(context, apiId),
                              absUrl: (u) => _absUrl(cfg, u),
                            ),
                            _ArtifactsTab(
                              artifacts: state.artifacts,
                              absUrl: (u) => _absUrl(cfg, u),
                            ),
                            _ApisTab(apis: state.apis.isNotEmpty
                                ? state.apis
                                : _resultRows(run: run, results: results)),
                          ],
                        ),
                      ),
                    ],
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

List<Map<String, dynamic>> _resultRows({
  required Map<String, dynamic> run,
  Object? results,
  List<Map<String, dynamic>> apis = const [],
}) {
  if (apis.isNotEmpty) return apis;
  final summary = run['api_summary'];
  if (summary is List) {
    return [
      for (final e in summary)
        if (e is Map) Map<String, dynamic>.from(e),
    ];
  }
  if (results is List) {
    return [
      for (final e in results)
        if (e is Map) Map<String, dynamic>.from(e),
    ];
  }
  if (results is Map) {
    final nested = results['apis'] ?? results['items'] ?? results['rows'];
    if (nested is List) {
      return [
        for (final e in nested)
          if (e is Map) Map<String, dynamic>.from(e),
      ];
    }
  }
  return const [];
}

num? _numOf(dynamic v) {
  if (v is num) return v;
  if (v is String) return num.tryParse(v);
  return null;
}

String _fmtMs(dynamic v) {
  final n = _numOf(v);
  if (n == null) return '—';
  return n.toStringAsFixed(n >= 100 ? 0 : 1);
}

/// Clean Playwright / stack errors for readable UI (strip ASCII boxes).
String _prettyError(String raw) {
  var text = raw
      .replaceAll(r'\n', '\n')
      .replaceAll(r'\r', '')
      .replaceAll('\r\n', '\n')
      .replaceAll('\r', '\n');
  final lines = text.split('\n');
  final out = <String>[];
  for (final line in lines) {
    final trimmed = line.trimRight();
    // Drop pure box-drawing / separator lines
    if (RegExp(r'^[-=_|+\\\s═║╔╗╚╝╠╣╟╢╤╧╪┌┐└┘├┤┬┴┼─│]+$').hasMatch(trimmed)) {
      continue;
    }
    // Strip leading/trailing box chars from content lines
    var cleaned = trimmed
        .replaceFirst(RegExp(r'^[|│║]\s?'), '')
        .replaceFirst(RegExp(r'\s?[|│║]\s*$'), '')
        .trimRight();
    if (cleaned.isEmpty) {
      if (out.isNotEmpty && out.last.isNotEmpty) out.add('');
      continue;
    }
    out.add(cleaned);
  }
  while (out.isNotEmpty && out.first.isEmpty) {
    out.removeAt(0);
  }
  while (out.isNotEmpty && out.last.isEmpty) {
    out.removeLast();
  }
  return out.join('\n');
}

class _OverviewTab extends StatelessWidget {
  const _OverviewTab({
    required this.run,
    this.results,
    this.baseline,
    this.apis = const [],
    required this.absUrl,
  });

  final Map<String, dynamic> run;
  final Object? results;
  final Map<String, dynamic>? baseline;
  final List<Map<String, dynamic>> apis;
  final String Function(String) absUrl;

  @override
  Widget build(BuildContext context) {
    final params = _runParams(run);
    final metrics = run['metrics_summary'] is Map
        ? Map<String, dynamic>.from(run['metrics_summary'] as Map)
        : (run['metrics'] is Map
            ? Map<String, dynamic>.from(run['metrics'] as Map)
            : <String, dynamic>{});
    final rows = _resultRows(run: run, results: results, apis: apis);
    final status = '${run['status'] ?? ''}';
    final grafana = '${run['grafana_url'] ?? ''}';
    final embed = '${run['grafana_embed_url'] ?? ''}';
    final isLive = status == 'running' || status == 'pending';

    var totalCalls = 0;
    var totalPass = 0;
    var totalFail = 0;
    for (final a in rows) {
      totalCalls += _intFrom(a['calls'] ?? a['count'] ?? a['iterations'], 0);
      totalPass += _intFrom(
        a['pass'] ?? a['pass_count'] ?? a['passed_count'] ?? a['ok'],
        0,
      );
      totalFail += _intFrom(
        a['fail'] ?? a['fail_count'] ?? a['failed_count'] ?? a['ko'],
        0,
      );
      if (a['checks_passed'] == true || a['passed'] == true) {
        if (_intFrom(a['pass'] ?? a['pass_count'] ?? a['passed_count'], 0) == 0 &&
            _intFrom(a['fail'] ?? a['fail_count'] ?? a['failed_count'], 0) == 0) {
          totalPass += 1;
        }
      }
      if (a['checks_passed'] == false || a['passed'] == false) {
        if (_intFrom(a['pass'] ?? a['pass_count'] ?? a['passed_count'], 0) == 0 &&
            _intFrom(a['fail'] ?? a['fail_count'] ?? a['failed_count'], 0) == 0) {
          totalFail += 1;
        }
      }
    }
    // Prefer run-level aggregates when present (list/detail API).
    final apiCount = _intFrom(run['api_count'], rows.isNotEmpty ? rows.length : totalCalls);
    final apiPass = _intFrom(run['api_pass_count'], totalPass);
    final apiFail = _intFrom(run['api_fail_count'], totalFail);
    final failPct = apiCount == 0 ? 0 : ((100 * apiFail) / apiCount).round();
    final err = '${run['error'] ?? ''}'.trim();

    return ListView(
      padding: const EdgeInsets.only(top: 8),
      children: [
        if (err.isNotEmpty) ...[
          GlassCard(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Icon(Icons.error_outline, color: Theme.of(context).colorScheme.error),
                    const SizedBox(width: 8),
                    Text(
                      'Error',
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            color: Theme.of(context).colorScheme.error,
                          ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                SelectableText(
                  _prettyError(err),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontFamily: 'Consolas',
                        height: 1.35,
                      ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
        ],
        GlassCard(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Parameters', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _kvChip('profile', '${run['run_profile'] ?? params['profile'] ?? '—'}'),
                  _kvChip('VUs', '${params['vus'] ?? run['vus'] ?? '—'}'),
                  _kvChip(
                    'calls',
                    '${params['iterations'] ?? params['calls'] ?? run['iterations'] ?? '—'}',
                  ),
                  _kvChip('duration', '${params['duration'] ?? run['duration'] ?? '—'}'),
                  _kvChip('service', '${run['service'] ?? '—'}'),
                  _kvChip('env', '${run['environment'] ?? '—'}'),
                  _kvChip('started', '${run['started_at'] ?? '—'}'),
                  _kvChip('finished', '${run['finished_at'] ?? '—'}'),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        GlassCard(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Outcome',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 12,
                runSpacing: 8,
                children: [
                  _metricTile(context, 'APIs', '$apiCount'),
                  _metricTile(context, 'Pass', '$apiPass', ok: true),
                  _metricTile(
                    context,
                    'Fail',
                    '$apiFail',
                    bad: apiFail > 0,
                  ),
                  _metricTile(
                    context,
                    'Fail%',
                    '$failPct%',
                    bad: failPct > 0,
                  ),
                ],
              ),
              if (metrics.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(
                  'Metrics (RPS · latency · data)',
                  style: Theme.of(context).textTheme.labelMedium,
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final e in metrics.entries.take(12))
                      Chip(
                        visualDensity: VisualDensity.compact,
                        label: Text('${e.key}: ${e.value}'),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 8),
        GlassCard(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Grafana', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 6),
              if (isLive)
                Text(
                  'Grafana unlocks when the run finishes.',
                  style: Theme.of(context).textTheme.bodySmall,
                )
              else if (grafana.isEmpty && embed.isEmpty)
                Text(
                  'Grafana URL unavailable.',
                  style: Theme.of(context).textTheme.bodySmall,
                )
              else ...[
                if (metrics.isEmpty)
                  Text(
                    'No chart data for this run.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 8,
                  children: [
                    if (grafana.isNotEmpty)
                      OutlinedButton.icon(
                        onPressed: () => launchUrl(Uri.parse(grafana)),
                        icon: const Icon(Icons.open_in_new, size: 16),
                        label: const Text('Open Grafana'),
                      ),
                    if (embed.isNotEmpty)
                      OutlinedButton.icon(
                        onPressed: () => launchUrl(Uri.parse(embed)),
                        icon: const Icon(Icons.fullscreen, size: 16),
                        label: const Text('Open embed / kiosk'),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
        Builder(
          builder: (context) {
            final runId = '${run['id'] ?? run['run_id'] ?? ''}'.trim();
            final reportUrl = '${run['ui_report_html_url'] ?? ''}'.trim();
            final hasUi = run['ui_report'] != null || reportUrl.isNotEmpty;
            if (!hasUi || runId.isEmpty) return const SizedBox.shrink();
            final href = reportUrl.isNotEmpty
                ? absUrl(reportUrl)
                : absUrl('/api/runs/$runId/artifacts/ui-report.html');
            return Padding(
              padding: const EdgeInsets.only(top: 8),
              child: GlassCard(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text('Playwright report', style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 8),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: FilledButton.tonalIcon(
                        onPressed: () => launchUrl(Uri.parse(href)),
                        icon: const Icon(Icons.language, size: 18),
                        label: const Text('Open UI report'),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
        if (baseline != null && baseline!.isNotEmpty) ...[
          const SizedBox(height: 8),
          _BaselineCard(baseline: baseline!),
        ],
        const SizedBox(height: 8),
        GlassCard(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Results table',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              if (rows.isEmpty)
                Text(
                  isLive
                      ? 'Results stream when APIs finish…'
                      : 'No API result rows for this run.',
                  style: Theme.of(context).textTheme.bodySmall,
                )
              else
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: DataTable(
                    headingRowHeight: 36,
                    dataRowMinHeight: 36,
                    dataRowMaxHeight: 48,
                    columns: const [
                      DataColumn(label: Text('API')),
                      DataColumn(label: Text('HTTP'), numeric: true),
                      DataColumn(label: Text('Calls'), numeric: true),
                      DataColumn(label: Text('Pass'), numeric: true),
                      DataColumn(label: Text('Fail'), numeric: true),
                      DataColumn(label: Text('Fail%'), numeric: true),
                      DataColumn(label: Text('Avg ms'), numeric: true),
                      DataColumn(label: Text('p90 ms'), numeric: true),
                      DataColumn(label: Text('Result')),
                    ],
                    rows: [
                      for (final a in rows)
                        DataRow(
                          cells: [
                            DataCell(
                              Text(
                                '${a['api_id'] ?? a['id'] ?? a['name'] ?? a['path'] ?? ''}',
                              ),
                            ),
                            DataCell(
                              Text(
                                '${a['http_status'] ?? a['status_code'] ?? a['status'] ?? '—'}',
                              ),
                            ),
                            DataCell(
                              Text(
                                '${a['calls'] ?? a['count'] ?? a['request_count'] ?? a['iterations'] ?? '—'}',
                              ),
                            ),
                            DataCell(
                              Text(
                                '${a['pass'] ?? a['pass_count'] ?? a['passed_count'] ?? a['ok'] ?? '—'}',
                              ),
                            ),
                            DataCell(
                              Text(
                                '${a['fail'] ?? a['fail_count'] ?? a['failed_count'] ?? a['ko'] ?? '—'}',
                              ),
                            ),
                            DataCell(
                              Text(
                                '${a['fail_pct'] ?? a['fail_rate'] ?? '—'}',
                              ),
                            ),
                            DataCell(
                              Text(
                                _fmtMs(
                                  a['avg_ms'] ?? a['avg'] ?? a['latency_avg'] ?? a['duration_ms'],
                                ),
                              ),
                            ),
                            DataCell(
                              Text(
                                _fmtMs(
                                  a['p90_ms'] ?? a['p90'] ?? a['latency_p90'],
                                ),
                              ),
                            ),
                            DataCell(
                              Text(
                                a['checks_passed'] == true || a['passed'] == true
                                    ? 'PASS'
                                    : (a['checks_passed'] == false || a['passed'] == false
                                        ? 'FAIL'
                                        : '${a['result'] ?? a['status'] ?? '—'}'),
                                style: TextStyle(
                                  fontWeight: FontWeight.w700,
                                  color: a['checks_passed'] == true || a['passed'] == true
                                      ? Colors.green
                                      : (a['checks_passed'] == false || a['passed'] == false
                                          ? Theme.of(context).colorScheme.error
                                          : null),
                                ),
                              ),
                            ),
                          ],
                        ),
                    ],
                  ),
                ),
              const SizedBox(height: 8),
              Text(
                'Tip: use Inspector tab for request/response of each call.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        ExpansionTile(
          title: const Text('Raw JSON'),
          children: [
            Padding(
              padding: const EdgeInsets.all(12),
              child: SelectableText(
                const JsonEncoder.withIndent('  ').convert({
                  'id': run['id'],
                  'status': run['status'],
                  'passed': run['passed'],
                  'api_count': run['api_count'],
                  'api_pass_count': run['api_pass_count'],
                  'api_fail_count': run['api_fail_count'],
                  'params': params,
                  'summary': run['summary'],
                  'results': results,
                  'error': run['error'],
                }),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _kvChip(String k, String v) => Chip(
        visualDensity: VisualDensity.compact,
        label: Text('$k: $v'),
      );

  Widget _metricTile(
    BuildContext context,
    String label,
    String value, {
    bool ok = false,
    bool bad = false,
  }) {
    final color = ok
        ? Colors.green
        : (bad ? Theme.of(context).colorScheme.error : AppColors.primary);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          Text(
            value,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
      ),
    );
  }
}

class _BaselineCard extends StatelessWidget {
  const _BaselineCard({required this.baseline});

  final Map<String, dynamic> baseline;

  @override
  Widget build(BuildContext context) {
    final ok = baseline['ok'] == true;
    final message = '${baseline['message'] ?? ''}';
    final prev = baseline['previous'] is Map
        ? Map<String, dynamic>.from(baseline['previous'] as Map)
        : null;
    final compare = baseline['compare'] is Map
        ? Map<String, dynamic>.from(baseline['compare'] as Map)
        : null;

    return GlassCard(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Baseline compare', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          if (!ok)
            Text(
              message.isEmpty ? 'No previous run for this profile.' : message,
              style: Theme.of(context).textTheme.bodySmall,
            )
          else ...[
            if (prev != null) ...[
              Text('Previous run', style: Theme.of(context).textTheme.labelMedium),
              const SizedBox(height: 6),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  Chip(
                    visualDensity: VisualDensity.compact,
                    label: Text(
                      'id ${(prev['id'] ?? '').toString().length > 8 ? prev['id'].toString().substring(0, 8) : prev['id']}',
                    ),
                  ),
                  Chip(
                    visualDensity: VisualDensity.compact,
                    label: Text('${prev['status'] ?? '—'}'),
                  ),
                  Chip(
                    visualDensity: VisualDensity.compact,
                    label: Text(
                      'APIs ${prev['api_count'] ?? '—'} · '
                      '${prev['api_pass_count'] ?? '—'}✓ / ${prev['api_fail_count'] ?? '—'}✗',
                    ),
                  ),
                  if (prev['passed'] == true)
                    const Chip(
                      visualDensity: VisualDensity.compact,
                      label: Text('passed'),
                      avatar: Icon(Icons.check, size: 14),
                    ),
                  if (prev['passed'] == false)
                    Chip(
                      visualDensity: VisualDensity.compact,
                      label: const Text('failed'),
                      avatar: Icon(
                        Icons.close,
                        size: 14,
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                ],
              ),
            ],
            if (compare != null) ...[
              const SizedBox(height: 12),
              Text('Delta', style: Theme.of(context).textTheme.labelMedium),
              const SizedBox(height: 6),
              _BaselineDelta(compare: compare),
            ],
            const SizedBox(height: 8),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: Text(
                'Raw baseline JSON',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              children: [
                SelectableText(
                  const JsonEncoder.withIndent('  ').convert(baseline),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontFamily: 'monospace',
                      ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _BaselineDelta extends StatelessWidget {
  const _BaselineDelta({required this.compare});

  final Map<String, dynamic> compare;

  @override
  Widget build(BuildContext context) {
    final deltas = <MapEntry<String, dynamic>>[];
    void collect(String prefix, Object? node) {
      if (node is Map) {
        for (final e in node.entries) {
          final key = prefix.isEmpty ? '${e.key}' : '$prefix.${e.key}';
          if (e.value is Map &&
              ((e.value as Map).containsKey('delta') ||
                  (e.value as Map).containsKey('a') ||
                  (e.value as Map).containsKey('b'))) {
            deltas.add(MapEntry(key, e.value));
          } else if (e.value is Map) {
            collect(key, e.value);
          } else if (e.key == 'delta' || e.key == 'diff') {
            deltas.add(MapEntry(prefix, node));
          }
        }
      }
    }

    collect('', compare);
    if (deltas.isEmpty) {
      // Fallback: show a few top-level compare keys as chips
      return Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final e in compare.entries.take(8))
            if (e.key != 'ok' && e.value is! Map)
              Chip(
                visualDensity: VisualDensity.compact,
                label: Text('${e.key}: ${e.value}'),
              ),
          if (compare.entries.every((e) => e.value is Map || e.key == 'ok'))
            Text(
              'See raw JSON for full compare payload.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
        ],
      );
    }

    return Column(
      children: [
        for (final e in deltas.take(12))
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              children: [
                Expanded(
                  child: Text(e.key, style: Theme.of(context).textTheme.bodySmall),
                ),
                Text(
                  e.value is Map
                      ? '${(e.value as Map)['a'] ?? '—'} → ${(e.value as Map)['b'] ?? '—'}'
                          '${(e.value as Map)['delta'] != null ? ' (Δ ${(e.value as Map)['delta']})' : ''}'
                      : '${e.value}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

bool _hasStructuredTrace(Map<String, dynamic> trace) {
  final req = trace['request'];
  final res = trace['response'];
  return req is Map || res is Map;
}

String _prettyJson(Object? value) {
  if (value == null) return '(empty)';
  try {
    if (value is String) {
      final t = value.trim();
      if (t.isEmpty) return '(empty)';
      try {
        return const JsonEncoder.withIndent('  ').convert(jsonDecode(t));
      } catch (_) {
        // Double-encoded JSON string (common in k6 traces)
        if ((t.startsWith('"') && t.endsWith('"')) || t.contains(r'\"')) {
          try {
            final once = jsonDecode(t);
            if (once is String) {
              return const JsonEncoder.withIndent('  ').convert(jsonDecode(once));
            }
            return const JsonEncoder.withIndent('  ').convert(once);
          } catch (_) {
            return value;
          }
        }
        return value;
      }
    }
    return const JsonEncoder.withIndent('  ').convert(value);
  } catch (_) {
    return '$value';
  }
}

Map<String, String> _stringHeaders(Object? raw) {
  if (raw is! Map) return {};
  final out = <String, String>{};
  for (final e in raw.entries) {
    final k = '${e.key}'.trim();
    if (k.isEmpty) continue;
    out[k] = '${e.value}';
  }
  return out;
}

String? _nonEmpty(Object? value) {
  if (value == null) return null;
  final s = '$value'.trim();
  return s.isEmpty ? null : s;
}

String _pathFromUrl(Object? url) {
  final raw = _nonEmpty(url);
  if (raw == null) return '';
  try {
    final uri = Uri.parse(raw);
    if (uri.hasScheme && uri.host.isNotEmpty) {
      final path = uri.path.isEmpty ? '/' : uri.path;
      return uri.hasQuery ? '$path?${uri.query}' : path;
    }
  } catch (_) {}
  return raw;
}

/// Human endpoint label for list + detail headers.
String _endpointLabel(Map<String, dynamic> t) {
  final path = _nonEmpty(t['path']) ?? _pathFromUrl(t['url']);
  final name = _nonEmpty(t['name']);
  final apiId = _nonEmpty(t['api_id']) ?? _nonEmpty(t['id']);
  // Prefer path; if name is just "METHOD path", skip duplicating method.
  if (path.isNotEmpty) return path;
  if (name != null) {
    final cleaned = name.replaceFirst(RegExp(r'^(GET|POST|PUT|PATCH|DELETE)\s+', caseSensitive: false), '');
    return cleaned.isNotEmpty ? cleaned : name;
  }
  if (apiId != null) return apiId;
  return _nonEmpty(t['url']) ?? '—';
}

String _traceUrl(Map<String, dynamic> t) {
  return _nonEmpty(t['url']) ??
      _nonEmpty(t['full_url']) ??
      _nonEmpty(t['path']) ??
      '';
}

Object? _traceStatus(Map<String, dynamic> t) {
  if (t['status_code'] != null) return t['status_code'];
  if (t['http_status'] != null) return t['http_status'];
  if (t['status'] is num || (t['status'] is String && int.tryParse('${t['status']}') != null)) {
    return t['status'];
  }
  if (t['response'] is Map) return (t['response'] as Map)['status'];
  return null;
}

String _bodyAsCurlData(Object? body) {
  if (body == null) return '';
  if (body is String) {
    final t = body.trim();
    if (t.isEmpty) return '';
    try {
      return const JsonEncoder.withIndent('  ').convert(jsonDecode(t));
    } catch (_) {
      return body;
    }
  }
  try {
    return const JsonEncoder.withIndent('  ').convert(body);
  } catch (_) {
    return '$body';
  }
}

String _shellDoubleQuote(String value) {
  return '"${value.replaceAll(r'\', r'\\').replaceAll('"', r'\"')}"';
}

String _curlFromTrace(Map<String, dynamic> trace) {
  final method = (_nonEmpty(trace['method']) ?? 'GET').toUpperCase();
  var url = _traceUrl(trace);
  if (url.isEmpty) return 'curl -sS -X $method';
  final req = trace['request'] is Map
      ? Map<String, dynamic>.from(trace['request'] as Map)
      : <String, dynamic>{};
  final headers = _stringHeaders(req['headers']);
  // Accept is useful default when traces omit headers
  if (headers.keys.every((k) => k.toLowerCase() != 'accept')) {
    headers.putIfAbsent('Accept', () => 'application/json');
  }
  final body = _bodyAsCurlData(req['body']);
  final parts = <String>[
    'curl',
    '-sS',
    '-X',
    method,
    _shellDoubleQuote(url),
  ];
  for (final e in headers.entries) {
    if (e.key.isEmpty) continue;
    parts.add('-H');
    parts.add(_shellDoubleQuote('${e.key}: ${e.value}'));
  }
  if (body.trim().isNotEmpty) {
    parts.add('--data-raw');
    parts.add(_shellDoubleQuote(body));
  }
  return parts.join(' ');
}

Color _statusColor(BuildContext context, Object? status) {
  final n = status is num ? status.toInt() : int.tryParse('$status');
  if (n == null) return Theme.of(context).colorScheme.outline;
  if (n >= 200 && n < 300) return Colors.green;
  if (n >= 400) return Theme.of(context).colorScheme.error;
  if (n >= 300) return Colors.orange;
  return Theme.of(context).colorScheme.outline;
}

bool _traceFailed(Map<String, dynamic> t) {
  final ok = t['ok'] ?? t['passed'] ?? t['checks_passed'];
  if (ok == false) return true;
  if (ok == true) return false;
  final code = _traceStatus(t);
  final n = code is num ? code.toInt() : int.tryParse('$code');
  return n != null && n >= 400;
}

class _InspectorTab extends StatelessWidget {
  const _InspectorTab({
    required this.traces,
    required this.selected,
    required this.selectedApiId,
    required this.failedOnly,
    required this.onFailedOnly,
    required this.onOpen,
    required this.onSavePayload,
    required this.absUrl,
  });

  final List<Map<String, dynamic>> traces;
  final Map<String, dynamic>? selected;
  final String? selectedApiId;
  final bool failedOnly;
  final ValueChanged<bool> onFailedOnly;
  final ValueChanged<Map<String, dynamic>> onOpen;
  final Future<void> Function(String apiId) onSavePayload;
  final String Function(String) absUrl;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            flex: 2,
            child: GlassCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: [
                  Container(
                    padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
                    decoration: BoxDecoration(
                      border: Border(
                        bottom: BorderSide(
                          color: scheme.outlineVariant.withValues(alpha: 0.5),
                        ),
                      ),
                    ),
                    child: Row(
                      children: [
                        Text(
                          'Calls',
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                        const Spacer(),
                        FilterChip(
                          label: const Text('Failed only'),
                          selected: failedOnly,
                          onSelected: onFailedOnly,
                          visualDensity: VisualDensity.compact,
                        ),
                      ],
                    ),
                  ),
                  Expanded(
                    child: traces.isEmpty
                        ? const Center(child: Text('No traces yet'))
                        : ListView.separated(
                            itemCount: traces.length,
                            separatorBuilder: (_, __) => Divider(
                              height: 1,
                              color: scheme.outlineVariant.withValues(alpha: 0.35),
                            ),
                            itemBuilder: (context, i) {
                              final t = traces[i];
                              final isUi = '${t['kind'] ?? ''}' == 'ui_step';
                              final method = (_nonEmpty(t['method']) ?? 'HTTP').toUpperCase();
                              final endpoint = isUi
                                  ? '${t['call_index'] ?? i + 1}. ${t['name'] ?? method}'
                                  : _endpointLabel(t);
                              final fullUrl = _traceUrl(t);
                              final statusCode = _traceStatus(t);
                              final failed = _traceFailed(t);
                              final selectedHere = identical(selected, t) ||
                                  (selected != null &&
                                      selected!['call_index'] == t['call_index'] &&
                                      selected!['api_id'] == t['api_id']);
                              final ms = t['timings'] is Map
                                  ? (t['timings'] as Map)['duration_ms']
                                  : (t['duration_ms'] ?? t['latency_ms']);
                              return Material(
                                color: selectedHere
                                    ? AppColors.primary.withValues(alpha: 0.10)
                                    : Colors.transparent,
                                child: InkWell(
                                  onTap: () => onOpen(t),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 12,
                                      vertical: 10,
                                    ),
                                    child: Row(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Container(
                                          constraints: const BoxConstraints(minWidth: 52),
                                          padding: const EdgeInsets.symmetric(
                                            horizontal: 8,
                                            vertical: 5,
                                          ),
                                          decoration: BoxDecoration(
                                            color: (failed
                                                    ? scheme.error
                                                    : AppColors.primary)
                                                .withValues(alpha: 0.12),
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Text(
                                            isUi ? 'UI' : method,
                                            textAlign: TextAlign.center,
                                            style: TextStyle(
                                              fontSize: 11,
                                              fontWeight: FontWeight.w800,
                                              color: failed ? scheme.error : AppColors.primary,
                                            ),
                                          ),
                                        ),
                                        const SizedBox(width: 10),
                                        Expanded(
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Text(
                                                endpoint,
                                                maxLines: 2,
                                                overflow: TextOverflow.ellipsis,
                                                style: const TextStyle(
                                                  fontWeight: FontWeight.w700,
                                                  fontSize: 13,
                                                  height: 1.25,
                                                ),
                                              ),
                                              if (!isUi &&
                                                  fullUrl.isNotEmpty &&
                                                  fullUrl != endpoint) ...[
                                                const SizedBox(height: 2),
                                                Text(
                                                  fullUrl,
                                                  maxLines: 1,
                                                  overflow: TextOverflow.ellipsis,
                                                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                                        fontSize: 11,
                                                        color: scheme.onSurface.withValues(alpha: 0.55),
                                                      ),
                                                ),
                                              ],
                                              const SizedBox(height: 4),
                                              Text(
                                                [
                                                  if (statusCode != null) '$statusCode',
                                                  if (ms != null) '${ms}ms',
                                                  failed ? 'FAIL' : 'PASS',
                                                ].join(' · '),
                                                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                                      fontWeight: FontWeight.w600,
                                                      color: failed
                                                          ? scheme.error
                                                          : Colors.green.shade700,
                                                    ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            flex: 3,
            child: GlassCard(
              padding: EdgeInsets.zero,
              child: selected == null
                  ? Center(
                      child: Text(
                        'Select a call to inspect request / response',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: scheme.onSurface.withValues(alpha: 0.55),
                            ),
                      ),
                    )
                  : _TraceDetailPanel(
                      trace: selected!,
                      apiId: selectedApiId,
                      onSavePayload: onSavePayload,
                      absUrl: absUrl,
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TraceDetailPanel extends StatelessWidget {
  const _TraceDetailPanel({
    required this.trace,
    required this.apiId,
    required this.onSavePayload,
    required this.absUrl,
  });

  final Map<String, dynamic> trace;
  final String? apiId;
  final Future<void> Function(String apiId) onSavePayload;
  final String Function(String) absUrl;

  bool get _isUiStep => '${trace['kind'] ?? ''}' == 'ui_step';

  Future<void> _copy(BuildContext context, String label, String text) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$label copied'), duration: const Duration(seconds: 1)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final method = (_nonEmpty(trace['method']) ?? 'GET').toUpperCase();
    final url = _traceUrl(trace);
    final endpoint = _endpointLabel(trace);
    final req = trace['request'] is Map
        ? Map<String, dynamic>.from(trace['request'] as Map)
        : <String, dynamic>{};
    final res = trace['response'] is Map
        ? Map<String, dynamic>.from(trace['response'] as Map)
        : <String, dynamic>{};
    final status = _traceStatus(trace);
    final ms = trace['timings'] is Map
        ? (trace['timings'] as Map)['duration_ms']
        : (trace['duration_ms'] ?? trace['latency_ms']);
    final structured = _hasStructuredTrace(trace) || !_isUiStep;
    final shotUrl = '${trace['screenshot_url'] ?? ''}';
    final reqBody = _prettyJson(req['body'] ?? (req.isEmpty ? null : req));
    final resBody = _prettyJson(res['body'] ?? (res.isEmpty ? null : res));
    final headersText = _prettyJson({
      'request': req['headers'] ?? {},
      'response': res['headers'] ?? {},
    });
    final curl = _isUiStep ? '' : _curlFromTrace(trace);
    final statusColor = _statusColor(context, status);
    final failed = _traceFailed(trace);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                (failed ? Theme.of(context).colorScheme.error : AppColors.primary)
                    .withValues(alpha: 0.08),
                Colors.transparent,
              ],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
            border: Border(
              bottom: BorderSide(
                color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.45),
              ),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 6,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.14),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      _isUiStep ? 'UI · $method' : method,
                      style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12),
                    ),
                  ),
                  if (status != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: statusColor.withValues(alpha: 0.14),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '$status',
                        style: TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: 12,
                          color: statusColor,
                        ),
                      ),
                    ),
                  if (ms != null)
                    Text(
                      '$ms ms',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                    ),
                  Text(
                    failed ? 'FAIL' : 'PASS',
                    style: TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 12,
                      color: failed
                          ? Theme.of(context).colorScheme.error
                          : Colors.green.shade700,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                endpoint,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              if (url.isNotEmpty && url != endpoint) ...[
                const SizedBox(height: 4),
                SelectableText(
                  url,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontFamily: 'Consolas',
                        height: 1.3,
                      ),
                ),
              ],
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  if (!_isUiStep)
                    FilledButton.tonalIcon(
                      onPressed: curl.isEmpty ? null : () => _copy(context, 'curl', curl),
                      icon: const Icon(Icons.terminal, size: 18),
                      label: const Text('Copy curl'),
                    ),
                  OutlinedButton.icon(
                    onPressed: () => _copy(context, 'Response', resBody),
                    icon: const Icon(Icons.copy_all, size: 18),
                    label: const Text('Copy response'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => _copy(context, 'Request', reqBody),
                    icon: const Icon(Icons.copy, size: 18),
                    label: const Text('Copy request'),
                  ),
                  if (!_isUiStep && apiId != null && apiId!.isNotEmpty)
                    OutlinedButton.icon(
                      onPressed: () => onSavePayload(apiId!),
                      icon: const Icon(Icons.save, size: 18),
                      label: const Text('Save payload'),
                    ),
                ],
              ),
            ],
          ),
        ),
        Expanded(
          child: structured
              ? DefaultTabController(
                  length: _isUiStep ? 4 : 5,
                  child: Column(
                    children: [
                      TabBar(
                        isScrollable: true,
                        tabs: _isUiStep
                            ? const [
                                Tab(text: 'Step'),
                                Tab(text: 'Result'),
                                Tab(text: 'Screenshot'),
                                Tab(text: 'Raw'),
                              ]
                            : const [
                                Tab(text: 'Request'),
                                Tab(text: 'Response'),
                                Tab(text: 'Headers'),
                                Tab(text: 'cURL'),
                                Tab(text: 'Raw'),
                              ],
                      ),
                      Expanded(
                        child: TabBarView(
                          children: _isUiStep
                              ? [
                                  _CodePane(text: reqBody, label: 'Step'),
                                  _CodePane(text: resBody, label: 'Result'),
                                  _ScreenshotPane(
                                    url: shotUrl.isEmpty ? null : absUrl(shotUrl),
                                  ),
                                  _CodePane(text: _prettyJson(trace), label: 'Raw'),
                                ]
                              : [
                                  _CodePane(text: reqBody, label: 'Request'),
                                  _CodePane(text: resBody, label: 'Response'),
                                  _CodePane(text: headersText, label: 'Headers'),
                                  _CodePane(text: curl, label: 'cURL', languageHint: 'bash'),
                                  _CodePane(text: _prettyJson(trace), label: 'Raw'),
                                ],
                        ),
                      ),
                    ],
                  ),
                )
              : _CodePane(text: _prettyJson(trace), label: 'Trace'),
        ),
      ],
    );
  }
}

class _ScreenshotPane extends StatelessWidget {
  const _ScreenshotPane({this.url});

  final String? url;

  @override
  Widget build(BuildContext context) {
    if (url == null || url!.isEmpty) {
      return Center(
        child: Text(
          'No screenshot for this step',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: () => launchUrl(Uri.parse(url!)),
              icon: const Icon(Icons.open_in_new, size: 16),
              label: const Text('Open'),
            ),
          ),
          Expanded(
            child: InteractiveViewer(
              minScale: 0.5,
              maxScale: 4,
              child: Image.network(
                url!,
                fit: BoxFit.contain,
                errorBuilder: (_, __, ___) => Center(
                  child: Text(
                    'Could not load screenshot',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
                loadingBuilder: (context, child, progress) {
                  if (progress == null) return child;
                  return const Center(child: CircularProgressIndicator(strokeWidth: 2));
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CodePane extends StatelessWidget {
  const _CodePane({
    required this.text,
    required this.label,
    this.languageHint,
  });

  final String text;
  final String label;
  final String? languageHint;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 8, 0),
          child: Row(
            children: [
              Text(
                label,
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              if (languageHint != null) ...[
                const SizedBox(width: 8),
                Chip(
                  label: Text(languageHint!),
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                ),
              ],
              const Spacer(),
              TextButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: text));
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('$label copied'),
                      duration: const Duration(seconds: 1),
                    ),
                  );
                },
                icon: const Icon(Icons.copy, size: 16),
                label: const Text('Copy'),
              ),
            ],
          ),
        ),
        Expanded(
          child: Container(
            margin: const EdgeInsets.fromLTRB(12, 4, 12, 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHighest.withValues(alpha: 0.55),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: scheme.outlineVariant.withValues(alpha: 0.45),
              ),
            ),
            child: SingleChildScrollView(
              child: SelectableText(
                text,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontFamily: 'Consolas',
                      height: 1.45,
                      fontSize: 12.5,
                    ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _ArtifactsTab extends StatelessWidget {
  const _ArtifactsTab({required this.artifacts, required this.absUrl});

  final List<Map<String, dynamic>> artifacts;
  final String Function(String) absUrl;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: EdgeInsets.zero,
      child: artifacts.isEmpty
          ? const Center(child: Text('None yet'))
          : ListView.separated(
              itemCount: artifacts.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, i) {
                final a = artifacts[i];
                final name = '${a['name'] ?? a['path'] ?? ''}';
                final url = '${a['url'] ?? ''}';
                final minio = '${a['minio_url'] ?? ''}';
                final kind = '${a['kind'] ?? a['type'] ?? ''}'.toLowerCase();
                return ListTile(
                  leading: Icon(
                    kind.contains('html') || kind.contains('report')
                        ? Icons.language
                        : (kind.contains('pdf')
                            ? Icons.picture_as_pdf
                            : (kind.contains('json')
                                ? Icons.data_object
                                : (kind.contains('image')
                                    ? Icons.image
                                    : Icons.attachment))),
                  ),
                  title: Text(name),
                  subtitle: Text('${a['kind'] ?? ''} · ${a['size'] ?? ''} bytes'),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (url.isNotEmpty)
                        IconButton(
                          icon: const Icon(Icons.download),
                          onPressed: () => launchUrl(Uri.parse(absUrl(url))),
                        ),
                      if (minio.isNotEmpty)
                        IconButton(
                          icon: const Icon(Icons.cloud),
                          onPressed: () => launchUrl(Uri.parse(minio)),
                        ),
                    ],
                  ),
                );
              },
            ),
    );
  }
}

class _ApisTab extends StatelessWidget {
  const _ApisTab({required this.apis});

  final List<Map<String, dynamic>> apis;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(8),
      child: apis.isEmpty
          ? const Center(child: Text('No API rows'))
          : SingleChildScrollView(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: DataTable(
                  headingRowHeight: 36,
                  dataRowMinHeight: 36,
                  dataRowMaxHeight: 48,
                  columns: const [
                    DataColumn(label: Text('API')),
                    DataColumn(label: Text('HTTP'), numeric: true),
                    DataColumn(label: Text('Calls'), numeric: true),
                    DataColumn(label: Text('Pass'), numeric: true),
                    DataColumn(label: Text('Fail'), numeric: true),
                    DataColumn(label: Text('Avg ms'), numeric: true),
                    DataColumn(label: Text('p90 ms'), numeric: true),
                    DataColumn(label: Text('Result')),
                  ],
                  rows: [
                    for (final a in apis)
                      DataRow(
                        cells: [
                          DataCell(
                            Text(
                              '${a['api_id'] ?? a['id'] ?? a['name'] ?? a['path'] ?? ''}',
                            ),
                          ),
                          DataCell(
                            Text(
                              '${a['http_status'] ?? a['status_code'] ?? a['status'] ?? '—'}',
                            ),
                          ),
                          DataCell(
                            Text('${a['calls'] ?? a['count'] ?? a['request_count'] ?? a['iterations'] ?? '—'}'),
                          ),
                          DataCell(
                            Text('${a['pass'] ?? a['pass_count'] ?? a['passed_count'] ?? a['ok'] ?? '—'}'),
                          ),
                          DataCell(
                            Text('${a['fail'] ?? a['fail_count'] ?? a['failed_count'] ?? a['ko'] ?? '—'}'),
                          ),
                          DataCell(
                            Text(
                              _fmtMs(a['avg_ms'] ?? a['avg'] ?? a['latency_avg'] ?? a['duration_ms']),
                            ),
                          ),
                          DataCell(
                            Text(
                              _fmtMs(a['p90_ms'] ?? a['p90'] ?? a['latency_p90']),
                            ),
                          ),
                          DataCell(
                            Text(
                              a['checks_passed'] == true || a['passed'] == true
                                  ? 'PASS'
                                  : (a['checks_passed'] == false || a['passed'] == false
                                      ? 'FAIL'
                                      : '${a['result'] ?? a['status'] ?? '—'}'),
                              style: TextStyle(
                                fontWeight: FontWeight.w700,
                                color: a['checks_passed'] == true || a['passed'] == true
                                    ? Colors.green
                                    : (a['checks_passed'] == false || a['passed'] == false
                                        ? Theme.of(context).colorScheme.error
                                        : null),
                              ),
                            ),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            ),
    );
  }
}
