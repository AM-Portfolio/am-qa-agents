import '../../../flow_graph/graph_layout.dart';

/// Build a display graph + evidence map from Playwright/UI run traces.
({
  Map<String, dynamic> graph,
  Map<String, Map<String, dynamic>> evidence,
  double totalLatencyMs,
  int passCount,
  int failCount,
}) uiRunGraphFromTraces(List<Map<String, dynamic>> traces) {
  final steps = <Map<String, dynamic>>[];
  for (final t in traces) {
    final kind = '${t['kind'] ?? ''}';
    if (kind == 'ui_step' || kind.isEmpty) {
      steps.add(t);
    }
  }
  steps.sort((a, b) {
    final ai = a['call_index'] is num
        ? (a['call_index'] as num).toInt()
        : int.tryParse('${a['call_index']}') ?? 0;
    final bi = b['call_index'] is num
        ? (b['call_index'] as num).toInt()
        : int.tryParse('${b['call_index']}') ?? 0;
    return ai.compareTo(bi);
  });

  final nodes = <Map<String, dynamic>>[
    {
      'id': kManualTriggerId,
      'kind': 'manual_trigger',
      'label': 'Start',
      'method': 'START',
      'x': defaultNodeX(0),
      'y': defaultNodeY(0),
    },
  ];
  final edges = <Map<String, dynamic>>[];
  final evidence = <String, Map<String, dynamic>>{};
  var prev = kManualTriggerId;
  var total = 0.0;
  var pass = 0;
  var fail = 0;

  for (var i = 0; i < steps.length; i++) {
    final t = steps[i];
    final id = '${t['api_id'] ?? 'step_${i + 1}'}';
    final name = '${t['name'] ?? t['method'] ?? id}';
    final method = '${t['method'] ?? 'STEP'}'.toUpperCase();
    nodes.add({
      'id': id,
      'kind': 'ui_step',
      'label': name,
      'method': method,
      'x': defaultNodeX(i + 1),
      'y': defaultNodeY(i + 1),
    });
    edges.add({
      'id': '$prev->$id',
      'from': prev,
      'to': id,
      'trigger': prev == kManualTriggerId,
    });
    final dur = durationMsFrom(t) ?? 0;
    total += dur;
    final passed = t['checks_passed'] == true;
    final failed = t['checks_passed'] == false || _traceFailed(t);
    if (passed && !failed) {
      pass++;
    } else if (failed) {
      fail++;
    }
    evidence[id] = {
      'status': failed ? 'fail' : (passed ? 'ok' : '${t['status'] ?? ''}'),
      'checks_passed': !failed && passed,
      'duration_ms': dur,
      'timings': {'duration_ms': dur},
      'request': t['request'],
      'response': t['response'],
      'error': t['error'],
      'screenshot_url': t['screenshot_url'],
      'trace': t,
    };
    prev = id;
  }

  return (
    graph: {
      'id': 'run_ui_graph',
      'nodes': nodes,
      'edges': edges,
    },
    evidence: evidence,
    totalLatencyMs: total,
    passCount: pass,
    failCount: fail,
  );
}

bool _traceFailed(Map<String, dynamic> t) {
  if (t['checks_passed'] == false) return true;
  final res = t['response'];
  if (res is Map) {
    final st = res['status'];
    final n = st is num ? st.toInt() : int.tryParse('$st');
    if (n != null && n >= 400) return true;
  }
  return false;
}

Map<String, dynamic>? traceForNodeId(
  Map<String, Map<String, dynamic>> evidence,
  String nodeId,
) {
  final ev = evidence[nodeId];
  if (ev == null) return null;
  final t = ev['trace'];
  if (t is Map) return Map<String, dynamic>.from(t);
  return null;
}
