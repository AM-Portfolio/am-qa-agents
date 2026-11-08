import 'package:flutter/material.dart';

/// Shared constants / helpers for n8n-style flow canvases.
const String kManualTriggerId = '__manual_trigger__';

Color? statusEdgeAccent(String? status) {
  switch ((status ?? '').toLowerCase()) {
    case 'ok':
    case 'pass':
    case 'passed':
    case 'completed':
      return const Color(0xFF2E7D32);
    case 'fail':
    case 'failed':
    case 'error':
      return const Color(0xFFC62828);
    case 'running':
      return const Color(0xFF1565C0);
    case 'skipped':
    case 'warn':
      return const Color(0xFF757575);
    default:
      return null;
  }
}

double defaultNodeX(int index) => 80.0 + index * 280.0;

double defaultNodeY(int index) => 120.0 + (index % 2) * 20.0;

/// Chain [nodeIds] left-to-right with sequential edges (trigger edge flagged).
List<Map<String, dynamic>> sequentialEdgesFor(List<String> nodeIds) {
  final edges = <Map<String, dynamic>>[];
  for (var i = 0; i < nodeIds.length - 1; i++) {
    final from = nodeIds[i];
    final to = nodeIds[i + 1];
    edges.add({
      'id': '$from->$to',
      'from': from,
      'to': to,
      if (from == kManualTriggerId) 'trigger': true,
    });
  }
  return edges;
}

/// Ensure a graph has a linear edge chain. Rebuilds edges when missing/empty.
Map<String, dynamic> ensureSequentialEdges(Map<String, dynamic> graph) {
  final nodes = [
    for (final n in (graph['nodes'] is List ? graph['nodes'] as List : const []))
      if (n is Map) Map<String, dynamic>.from(n),
  ];
  if (nodes.isEmpty) return graph;
  final existing = [
    for (final e in (graph['edges'] is List ? graph['edges'] as List : const []))
      if (e is Map) Map<String, dynamic>.from(e),
  ];
  if (existing.isNotEmpty) {
    return {...graph, 'nodes': nodes, 'edges': existing};
  }
  // Prefer left-to-right by x, then original list order.
  final orderIdx = List<int>.generate(nodes.length, (i) => i);
  orderIdx.sort((a, b) {
    final ax = nodes[a]['x'] is num
        ? (nodes[a]['x'] as num).toDouble()
        : a * 280.0;
    final bx = nodes[b]['x'] is num
        ? (nodes[b]['x'] as num).toDouble()
        : b * 280.0;
    final c = ax.compareTo(bx);
    return c != 0 ? c : a.compareTo(b);
  });
  final ids = [for (final i in orderIdx) '${nodes[i]['id']}'];
  // Keep trigger first when present.
  final triggerIdx = ids.indexOf(kManualTriggerId);
  if (triggerIdx > 0) {
    ids
      ..removeAt(triggerIdx)
      ..insert(0, kManualTriggerId);
  }
  return {...graph, 'nodes': nodes, 'edges': sequentialEdgesFor(ids)};
}

/// Build sequential nodes/edges from step + verification string lists.
Map<String, dynamic> graphFromStepLists({
  required String flowId,
  required List<String> steps,
  List<String> verifications = const [],
  Map<String, dynamic>? existingGraph,
}) {
  if (existingGraph != null) {
    final nodes = existingGraph['nodes'];
    if (nodes is List && nodes.isNotEmpty) {
      return ensureSequentialEdges({
        'id': flowId,
        'nodes': [
          for (final n in nodes)
            if (n is Map) Map<String, dynamic>.from(n),
        ],
        'edges': [
          for (final e in (existingGraph['edges'] is List
              ? existingGraph['edges'] as List
              : const []))
            if (e is Map) Map<String, dynamic>.from(e),
        ],
      });
    }
  }

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
  final ids = <String>[kManualTriggerId];
  var i = 1;
  for (final step in steps) {
    final label = step.trim();
    if (label.isEmpty) continue;
    final id = 'step_$i';
    nodes.add({
      'id': id,
      'kind': 'ui_step',
      'label': label,
      'method': 'STEP',
      'x': defaultNodeX(i),
      'y': defaultNodeY(i),
    });
    ids.add(id);
    i++;
  }
  for (final v in verifications) {
    final label = v.trim();
    if (label.isEmpty) continue;
    final id = 'verify_$i';
    nodes.add({
      'id': id,
      'kind': 'verification',
      'label': label,
      'method': 'VERIFY',
      'x': defaultNodeX(i),
      'y': defaultNodeY(i),
    });
    ids.add(id);
    i++;
  }
  return {'id': flowId, 'nodes': nodes, 'edges': sequentialEdgesFor(ids)};
}

/// Derive documentation `steps` / `verifications` lists from a graph.
({List<String> steps, List<String> verifications}) listsFromGraph(
  Map<String, dynamic> graph,
) {
  final nodes = graph['nodes'];
  final edges = graph['edges'];
  if (nodes is! List) {
    return (steps: <String>[], verifications: <String>[]);
  }
  final byId = <String, Map<String, dynamic>>{};
  for (final n in nodes) {
    if (n is Map) {
      final m = Map<String, dynamic>.from(n);
      byId['${m['id']}'] = m;
    }
  }
  // Walk from trigger via edges for order; fallback to list order.
  final order = <String>[];
  if (edges is List && edges.isNotEmpty) {
    final outs = <String, List<String>>{};
    for (final e in edges) {
      if (e is! Map) continue;
      final from = '${e['from']}';
      final to = '${e['to']}';
      outs.putIfAbsent(from, () => []).add(to);
    }
    var cur = kManualTriggerId;
    final seen = <String>{cur};
    while (true) {
      final nexts = outs[cur];
      if (nexts == null || nexts.isEmpty) break;
      final next = nexts.first;
      if (!seen.add(next)) break;
      order.add(next);
      cur = next;
    }
  }
  if (order.isEmpty) {
    for (final id in byId.keys) {
      if (id != kManualTriggerId) order.add(id);
    }
  }
  final steps = <String>[];
  final verifications = <String>[];
  for (final id in order) {
    final n = byId[id];
    if (n == null) continue;
    final kind = '${n['kind'] ?? 'ui_step'}';
    final label = '${n['label'] ?? id}'.trim();
    if (label.isEmpty || kind == 'manual_trigger') continue;
    if (kind == 'verification') {
      verifications.add(label);
    } else {
      steps.add(label);
    }
  }
  return (steps: steps, verifications: verifications);
}

double? durationMsFrom(Object? value) {
  if (value is Map) {
    final t = value['timings'];
    if (t is Map && t['duration_ms'] != null) {
      final n = t['duration_ms'];
      if (n is num) return n.toDouble();
      return double.tryParse('$n');
    }
    final d = value['duration_ms'] ?? value['latency_ms'];
    if (d is num) return d.toDouble();
    return double.tryParse('$d');
  }
  return null;
}
