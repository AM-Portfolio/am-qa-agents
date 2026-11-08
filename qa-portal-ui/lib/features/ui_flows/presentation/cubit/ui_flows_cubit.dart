import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../execute/data/execute_repository.dart';
import '../../../flow_graph/graph_layout.dart';
import '../../../runs/data/runs_repository.dart';
import '../../data/ui_flows_repository.dart';
import 'ui_flows_state.dart';

final _flowIdPattern = RegExp(r'^[A-Z0-9_]+$');

class UiFlowsCubit extends Cubit<UiFlowsState> {
  UiFlowsCubit(this._repo, this._execute, this._runs)
      : super(const UiFlowsState());

  final UiFlowsRepository _repo;
  final ExecuteRepository _execute;
  final RunsRepository _runs;
  Timer? _poll;

  Future<void> load({String? keepSelected}) async {
    emit(state.copyWith(loading: true, clearError: true));
    try {
      final cat = await _repo.catalog();
      final flows = <Map<String, dynamic>>[];
      final seen = <String>{};

      void addMap(Map raw) {
        final m = Map<String, dynamic>.from(raw);
        final id = '${m['id'] ?? ''}'.trim();
        if (id.isEmpty) return;
        if (!seen.add(id)) {
          final idx = flows.indexWhere((f) => '${f['id']}' == id);
          if (idx >= 0 && m.keys.length >= flows[idx].keys.length) {
            flows[idx] = m;
          }
          return;
        }
        flows.add(m);
      }

      void addStub(String id) {
        final trimmed = id.trim();
        if (trimmed.isEmpty || seen.contains(trimmed)) return;
        seen.add(trimmed);
        flows.add({'id': trimmed, 'label': trimmed});
      }

      for (final key in ['flows', 'custom_flows']) {
        final list = cat[key];
        if (list is! List) continue;
        for (final e in list) {
          if (e is Map) addMap(e);
        }
      }
      for (final key in ['deterministic', 'release_gate']) {
        final list = cat[key];
        if (list is! List) continue;
        for (final e in list) {
          if (e is Map) {
            addMap(e);
          } else if (e is String) {
            addStub(e);
          }
        }
      }

      final suites = <Map<String, dynamic>>[];
      final suiteSeen = <String>{};
      final rawSuites = cat['suites'];
      if (rawSuites is List) {
        for (final e in rawSuites) {
          if (e is Map) {
            final m = Map<String, dynamic>.from(e);
            final id = '${m['id'] ?? ''}'.trim();
            if (id.isEmpty || !suiteSeen.add(id)) continue;
            suites.add(m);
          } else if (e is String) {
            final id = e.trim();
            if (id.isEmpty || !suiteSeen.add(id)) continue;
            suites.add({'id': id, 'label': id});
          }
        }
      }
      final agent = cat['agent'];
      final agentMap = agent is Map ? Map<String, dynamic>.from(agent) : null;
      final online = agentMap?['online'] == true || cat['agent_online'] == true;
      final url = agentMap?['url']?.toString() ?? cat['agent_url']?.toString();
      final err = agentMap?['error']?.toString() ?? cat['error']?.toString();

      final prefer = keepSelected ?? state.selectedFlowId;
      final selected = (prefer != null && flows.any((f) => '${f['id']}' == prefer))
          ? prefer
          : (flows.isNotEmpty ? '${flows.first['id']}' : null);

      emit(
        state.copyWith(
          loading: false,
          flows: flows,
          suites: suites,
          agentOnline: online,
          agentUrl: url,
          error: err,
          selectedFlowId: selected,
        ),
      );
      if (selected != null) {
        _loadGraphFor(selected, flows);
      }
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }

  void selectFlow(String id) {
    if (id == state.selectedFlowId) return;
    _poll?.cancel();
    emit(
      state.copyWith(
        selectedFlowId: id,
        graphDirty: false,
        clearSelectedNode: true,
        clearRun: true,
        running: false,
      ),
    );
    _loadGraphFor(id, state.flows);
  }

  void setBottomTab(int tab) => emit(state.copyWith(bottomTab: tab));

  void _loadGraphFor(String id, List<Map<String, dynamic>> flows) {
    Map<String, dynamic>? flow;
    for (final f in flows) {
      if ('${f['id']}' == id) {
        flow = f;
        break;
      }
    }
    if (flow == null) {
      emit(state.copyWith(clearGraph: true));
      return;
    }
    final steps = <String>[
      for (final s in (flow['steps'] is List ? flow['steps'] as List : const []))
        '$s'.trim(),
    ].where((s) => s.isNotEmpty).toList();
    final verifs = <String>[
      for (final s
          in (flow['verifications'] is List ? flow['verifications'] as List : const []))
        '$s'.trim(),
    ].where((s) => s.isNotEmpty).toList();
    final existing = flow['graph'] is Map
        ? Map<String, dynamic>.from(flow['graph'] as Map)
        : null;
    final graph = graphFromStepLists(
      flowId: id,
      steps: steps,
      verifications: verifs,
      existingGraph: existing,
    );
    emit(state.copyWith(graph: graph, graphDirty: false));
  }

  void selectNode(String id) {
    emit(state.copyWith(selectedNodeId: id));
  }

  void addStepAfter(String afterId) {
    final g = state.graph;
    if (g == null) return;
    final nodes = [
      for (final n in (g['nodes'] is List ? g['nodes'] as List : const []))
        if (n is Map) Map<String, dynamic>.from(n),
    ];
    final edges = [
      for (final e in (g['edges'] is List ? g['edges'] as List : const []))
        if (e is Map) Map<String, dynamic>.from(e),
    ];
    final idx = nodes.indexWhere((n) => '${n['id']}' == afterId);
    if (idx < 0) return;
    final newId = 'step_${DateTime.now().millisecondsSinceEpoch}';
    final baseX = (nodes[idx]['x'] is num)
        ? (nodes[idx]['x'] as num).toDouble()
        : defaultNodeX(idx);
    final baseY = (nodes[idx]['y'] is num)
        ? (nodes[idx]['y'] as num).toDouble()
        : defaultNodeY(idx);
    final newNode = {
      'id': newId,
      'kind': 'ui_step',
      'label': 'New step',
      'method': 'STEP',
      'x': baseX + 280,
      'y': baseY,
    };
    // Rewire: afterId -> newId -> previous targets of afterId
    final outgoing = edges.where((e) => '${e['from']}' == afterId).toList();
    edges.removeWhere((e) => '${e['from']}' == afterId);
    edges.add({
      'id': '$afterId->$newId',
      'from': afterId,
      'to': newId,
      'trigger': afterId == kManualTriggerId,
    });
    for (final e in outgoing) {
      edges.add({
        'id': '$newId->${e['to']}',
        'from': newId,
        'to': '${e['to']}',
      });
    }
    nodes.insert(idx + 1, newNode);
    emit(
      state.copyWith(
        graph: {...g, 'nodes': nodes, 'edges': edges},
        graphDirty: true,
        selectedNodeId: newId,
      ),
    );
  }

  void deleteNode(String nodeId) {
    if (nodeId == kManualTriggerId) return;
    final g = state.graph;
    if (g == null) return;
    final nodes = [
      for (final n in (g['nodes'] is List ? g['nodes'] as List : const []))
        if (n is Map && '${n['id']}' != nodeId) Map<String, dynamic>.from(n),
    ];
    final edgesIn = [
      for (final e in (g['edges'] is List ? g['edges'] as List : const []))
        if (e is Map) Map<String, dynamic>.from(e),
    ];
    final preds = [
      for (final e in edgesIn)
        if ('${e['to']}' == nodeId) '${e['from']}',
    ];
    final succs = [
      for (final e in edgesIn)
        if ('${e['from']}' == nodeId) '${e['to']}',
    ];
    final edges = [
      for (final e in edgesIn)
        if ('${e['from']}' != nodeId && '${e['to']}' != nodeId) e,
    ];
    for (final p in preds) {
      for (final s in succs) {
        edges.add({
          'id': '$p->$s',
          'from': p,
          'to': s,
          'trigger': p == kManualTriggerId,
        });
      }
    }
    emit(
      state.copyWith(
        graph: {...g, 'nodes': nodes, 'edges': edges},
        graphDirty: true,
        clearSelectedNode: state.selectedNodeId == nodeId,
      ),
    );
  }

  void renameSelectedNode(String label) {
    final nid = state.selectedNodeId;
    final g = state.graph;
    if (nid == null || g == null || nid == kManualTriggerId) return;
    final fixed = <Map<String, dynamic>>[];
    for (final n in (g['nodes'] is List ? g['nodes'] as List : const [])) {
      if (n is! Map) continue;
      final m = Map<String, dynamic>.from(n);
      if ('${m['id']}' == nid) m['label'] = label.trim();
      fixed.add(m);
    }
    emit(
      state.copyWith(
        graph: {...g, 'nodes': fixed},
        graphDirty: true,
      ),
    );
  }

  Future<void> saveGraph() async {
    final id = state.selectedFlowId;
    final g = state.graph;
    final flow = state.selectedFlow;
    if (id == null || g == null || flow == null) return;
    emit(state.copyWith(saving: true, clearError: true));
    try {
      final lists = listsFromGraph(g);
      final body = <String, dynamic>{
        'id': id,
        'label': flow['label'] ?? id,
        'group': flow['group'] ?? 'Custom',
        'summary': flow['summary'] ?? '',
        'graph': g,
        'steps': lists.steps,
        'verifications': lists.verifications,
      };
      final runsAs = '${flow['runs_as'] ?? id}'.trim();
      if (flow['custom'] == true || runsAs != id) {
        body['runs_as'] = runsAs.isEmpty ? id : runsAs;
      }
      final exists = state.flows.any((f) => '${f['id']}' == id);
      if (exists) {
        await _repo.updateFlow(id, body);
      } else {
        await _repo.createFlow(body);
      }
      await load(keepSelected: id);
      emit(state.copyWith(saving: false, graphDirty: false));
    } catch (e) {
      emit(state.copyWith(saving: false, error: e.toString()));
    }
  }

  Future<void> saveFlow(Map<String, dynamic> body) async {
    final id = body['id']?.toString().trim() ?? '';
    if (id.isEmpty) throw ArgumentError('Flow id required');
    if (!_flowIdPattern.hasMatch(id)) {
      throw ArgumentError('Flow id must match [A-Z0-9_]+');
    }
    final exists = state.flows.any((f) => '${f['id']}' == id);
    if (exists) {
      await _repo.updateFlow(id, body);
    } else {
      await _repo.createFlow(body);
    }
    await load(keepSelected: id);
  }

  Future<void> saveSuite(Map<String, dynamic> body) async {
    final id = body['id']?.toString().trim() ?? '';
    if (id.isEmpty) throw ArgumentError('Suite id required');
    if (!_flowIdPattern.hasMatch(id)) {
      throw ArgumentError('Suite id must match [A-Z0-9_]+');
    }
    final profiles = body['profiles'];
    if (profiles is! List || profiles.isEmpty) {
      throw ArgumentError('Suite profiles must be a non-empty list');
    }
    final exists = state.suites.any((s) => '${s['id']}' == id);
    if (exists) {
      await _repo.updateSuite(id, body);
    } else {
      await _repo.createSuite(body);
    }
    await load(keepSelected: state.selectedFlowId);
  }

  Future<void> deleteFlow(String id, {bool reset = false}) async {
    await _repo.deleteFlow(id, reset: reset);
    await load();
  }

  Future<void> deleteSuite(String id, {bool reset = false}) async {
    await _repo.deleteSuite(id, reset: reset);
    await load(keepSelected: state.selectedFlowId);
  }

  Future<void> runSelected() async {
    final flowId = state.selectedFlowId;
    final flow = state.selectedFlow;
    if (flowId == null || flow == null || state.running) return;
    final profile = '${flow['runs_as'] ?? flowId}'.trim();
    _poll?.cancel();
    emit(
      state.copyWith(
        running: true,
        clearError: true,
        clearRun: true,
        bottomTab: 0,
        runStatus: 'running',
        evidenceByNodeId: _runningEvidence(state.graph),
      ),
    );
    try {
      final configs = await _execute.listConfigs();
      final cfg = _findPlaywrightConfig(configs);
      if (cfg == null) {
        emit(
          state.copyWith(
            running: false,
            error: 'No playwright/mixed config found',
            clearRun: true,
          ),
        );
        return;
      }
      final out = await _execute.execute(
        configId: '${cfg['id']}',
        testType: 'playwright',
        uiProfile: profile.isEmpty ? flowId : profile,
      );
      final runId = '${out['id'] ?? out['run_id'] ?? ''}'.trim();
      if (runId.isEmpty) {
        emit(
          state.copyWith(
            running: false,
            error: 'Execute returned no run id',
          ),
        );
        return;
      }
      emit(state.copyWith(runId: runId, runStatus: 'running'));
      _poll = Timer.periodic(const Duration(milliseconds: 900), (_) {
        unawaited(_pollRun(runId));
      });
      await _pollRun(runId);
    } catch (e) {
      _poll?.cancel();
      emit(state.copyWith(running: false, error: e.toString()));
    }
  }

  Future<void> runSuite(String suiteId) async {
    if (suiteId.isEmpty || state.running) return;
    _poll?.cancel();
    emit(
      state.copyWith(
        running: true,
        clearError: true,
        clearRun: true,
        bottomTab: 0,
      ),
    );
    try {
      final configs = await _execute.listConfigs();
      final cfg = _findPlaywrightConfig(configs);
      if (cfg == null) {
        emit(
          state.copyWith(
            running: false,
            error: 'No playwright/mixed config found',
          ),
        );
        return;
      }
      final out = await _execute.execute(
        configId: '${cfg['id']}',
        testType: 'playwright',
        uiSuite: suiteId,
      );
      final runId = '${out['id'] ?? out['run_id'] ?? ''}'.trim();
      if (runId.isEmpty) {
        emit(
          state.copyWith(
            running: false,
            error: 'Execute returned no run id',
          ),
        );
        return;
      }
      emit(state.copyWith(runId: runId, runStatus: 'running'));
      _poll = Timer.periodic(const Duration(milliseconds: 900), (_) {
        unawaited(_pollRun(runId));
      });
      await _pollRun(runId);
    } catch (e) {
      _poll?.cancel();
      emit(state.copyWith(running: false, error: e.toString()));
    }
  }

  Future<Map<String, dynamic>> loadObsLogs() async {
    final id = state.runId;
    if (id == null || id.isEmpty) {
      return {'available': false, 'reason': 'no_run', 'lines': []};
    }
    return _runs.obsLogs(id);
  }

  Future<void> _pollRun(String runId) async {
    try {
      final run = await _runs.getRun(runId);
      final status = '${run['status'] ?? ''}'.toLowerCase();
      List<Map<String, dynamic>> traces = const [];
      try {
        traces = await _runs.traces(runId, limit: 200);
      } catch (_) {
        // Traces may lag behind status while the agent is still writing.
      }
      final evidence = _evidenceOntoGraph(state.graph, traces, running: !_terminal(status));
      final summary = _summaryLine(run, traces);
      final errRaw = '${run['error_short'] ?? run['error'] ?? ''}'.trim();
      final done = _terminal(status);
      final obs = run['observability_resources'] is Map
          ? Map<String, dynamic>.from(run['observability_resources'] as Map)
          : null;
      emit(
        state.copyWith(
          runId: runId,
          runStatus: status.isEmpty ? 'running' : status,
          runSummary: summary,
          runError: errRaw.isEmpty ? null : errRaw,
          runTraceId: '${run['trace_id'] ?? ''}'.trim().isEmpty
              ? null
              : '${run['trace_id']}'.trim(),
          runCorrelationId: '${run['correlation_id'] ?? ''}'.trim().isEmpty
              ? null
              : '${run['correlation_id']}'.trim(),
          observabilityResources: obs,
          traces: traces,
          evidenceByNodeId: evidence,
          running: !done,
        ),
      );
      if (done) {
        _poll?.cancel();
      }
    } catch (e) {
      _poll?.cancel();
      emit(state.copyWith(running: false, error: e.toString()));
    }
  }

  bool _terminal(String status) {
    const done = {
      'finished',
      'completed',
      'passed',
      'failed',
      'error',
      'stopped',
      'cancelled',
      'canceled',
    };
    return done.contains(status.toLowerCase());
  }

  Map<String, Map<String, dynamic>> _runningEvidence(Map<String, dynamic>? graph) {
    final out = <String, Map<String, dynamic>>{};
    if (graph == null) return out;
    out[kManualTriggerId] = {'status': 'ok', 'duration_ms': 0.0};
    final ids = _orderedStepIds(graph);
    // Only the first step is active; the rest stay pending until traces arrive.
    if (ids.isNotEmpty) {
      out[ids.first] = {'status': 'running'};
    }
    return out;
  }

  List<String> _orderedStepIds(Map<String, dynamic> graph) {
    final nodes = <String, Map<String, dynamic>>{};
    for (final n in (graph['nodes'] is List ? graph['nodes'] as List : const [])) {
      if (n is Map) nodes['${n['id']}'] = Map<String, dynamic>.from(n);
    }
    final outs = <String, List<String>>{};
    for (final e in (graph['edges'] is List ? graph['edges'] as List : const [])) {
      if (e is! Map) continue;
      outs.putIfAbsent('${e['from']}', () => []).add('${e['to']}');
    }
    final order = <String>[];
    var cur = kManualTriggerId;
    final seen = <String>{cur};
    while (true) {
      final nexts = outs[cur];
      if (nexts == null || nexts.isEmpty) break;
      final next = nexts.first;
      if (!seen.add(next)) break;
      final kind = '${nodes[next]?['kind'] ?? 'ui_step'}';
      if (kind != 'manual_trigger') order.add(next);
      cur = next;
    }
    if (order.isEmpty) {
      final rest = nodes.entries
          .where(
            (e) =>
                e.key != kManualTriggerId &&
                '${e.value['kind']}' != 'manual_trigger',
          )
          .toList()
        ..sort((a, b) {
          final ax = a.value['x'] is num
              ? (a.value['x'] as num).toDouble()
              : 0.0;
          final bx = b.value['x'] is num
              ? (b.value['x'] as num).toDouble()
              : 0.0;
          return ax.compareTo(bx);
        });
      for (final e in rest) {
        order.add(e.key);
      }
    }
    return order;
  }

  Map<String, Map<String, dynamic>> _evidenceOntoGraph(
    Map<String, dynamic>? graph,
    List<Map<String, dynamic>> traces, {
    required bool running,
  }) {
    final out = <String, Map<String, dynamic>>{
      kManualTriggerId: {'status': 'ok', 'duration_ms': 0.0},
    };
    if (graph == null) return out;
    final steps = [
      for (final t in traces)
        if ('${t['kind'] ?? ''}' == 'ui_step' || '${t['kind'] ?? ''}'.isEmpty)
          t,
    ]..sort((a, b) {
        final ai = a['call_index'] is num
            ? (a['call_index'] as num).toInt()
            : int.tryParse('${a['call_index']}') ?? 0;
        final bi = b['call_index'] is num
            ? (b['call_index'] as num).toInt()
            : int.tryParse('${b['call_index']}') ?? 0;
        return ai.compareTo(bi);
      });
    final ids = _orderedStepIds(graph);
    var failedAt = -1;
    for (var i = 0; i < ids.length; i++) {
      final id = ids[i];
      if (i >= steps.length) {
        // Sequential: only the next unfinished step is running.
        if (running && failedAt < 0 && i == steps.length) {
          out[id] = {'status': 'running'};
        }
        continue;
      }
      final t = steps[i];
      final failed = t['checks_passed'] == false;
      final passed = t['checks_passed'] == true;
      final dur = durationMsFrom(t) ?? 0.0;
      if (failed && failedAt < 0) failedAt = i;
      out[id] = {
        'status': failed ? 'fail' : (passed ? 'ok' : '${t['status'] ?? 'ok'}'),
        'checks_passed': !failed && passed,
        'duration_ms': dur,
        'timings': {'duration_ms': dur},
        'request': t['request'],
        'response': t['response'],
        'error': t['error'],
        'screenshot_url': t['screenshot_url'],
        'trace': t,
      };
    }
    return out;
  }

  String _summaryLine(Map<String, dynamic> run, List<Map<String, dynamic>> traces) {
    final status = '${run['status'] ?? ''}';
    var pass = 0;
    var fail = 0;
    for (final t in traces) {
      if (t['checks_passed'] == true) {
        pass++;
      } else if (t['checks_passed'] == false) {
        fail++;
      }
    }
    final err = '${run['error_short'] ?? run['error'] ?? ''}'.trim();
    final errOne = err.isEmpty
        ? ''
        : err.split('\n').first.trim().replaceAll(RegExp(r'\s+'), ' ');
    final parts = <String>[
      if (status.isNotEmpty) status,
      'passed=$pass',
      if (fail > 0) 'failed=$fail',
      if (errOne.isNotEmpty)
        errOne.length > 120 ? '${errOne.substring(0, 120)}…' : errOne,
    ];
    return parts.join(' · ');
  }

  Map<String, dynamic>? _findPlaywrightConfig(
    List<Map<String, dynamic>> configs,
  ) {
    bool isUi(Map<String, dynamic> c) {
      final tt = '${c['test_type'] ?? 'k6'}'.toLowerCase();
      return tt == 'playwright' || tt == 'mixed';
    }

    for (final c in configs) {
      if (isUi(c) && '${c['service'] ?? ''}' == 'am-modern-ui') return c;
    }
    for (final c in configs) {
      if (isUi(c)) return c;
    }
    return null;
  }

  @override
  Future<void> close() {
    _poll?.cancel();
    return super.close();
  }
}
