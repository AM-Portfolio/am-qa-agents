part of 'ui_flows_cubit.dart';

extension UiFlowsCubitRun on UiFlowsCubit {
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
}
