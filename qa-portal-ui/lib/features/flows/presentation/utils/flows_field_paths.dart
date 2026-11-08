// Flatten JSON into JSONPath-ish keys usable by the flows runner capture map.

List<String> flattenResponsePaths(
  Object? data, {
  String root = '\$',
  int maxDepth = 5,
  int maxLeaves = 80,
}) {
  final out = <String>[];
  void walk(Object? node, String path, int depth) {
    if (out.length >= maxLeaves || depth > maxDepth) return;
    if (node is Map) {
      if (node.isEmpty) {
        out.add(path);
        return;
      }
      for (final e in node.entries) {
        final key = '${e.key}';
        final next = path == '\$' ? '\$.$key' : '$path.$key';
        walk(e.value, next, depth + 1);
      }
      return;
    }
    if (node is List) {
      if (node.isEmpty) {
        out.add(path);
        return;
      }
      final n = node.length < 3 ? node.length : 3;
      for (var i = 0; i < n; i++) {
        final next = '$path[$i]';
        walk(node[i], next, depth + 1);
      }
      return;
    }
    out.add(path);
  }

  walk(data, root, 0);
  // Prefer `$[0].x` form when root was `$` and data is a list — already encoded.
  return out;
}

/// Input slots the next API card can consume (path / query / body).
class FlowInputSlot {
  const FlowInputSlot({
    required this.name,
    required this.kind,
    this.hint,
  });

  final String name;
  /// path | query | body
  final String kind;
  final String? hint;

  String get label => '$name ($kind)';

  @override
  bool operator ==(Object other) =>
      other is FlowInputSlot && other.name == name && other.kind == kind;

  @override
  int get hashCode => Object.hash(name, kind);
}

final _pathParamRe = RegExp(r'\{([^{}/]+)\}');

List<FlowInputSlot> inputSlotsForNode(Map<String, dynamic> node) {
  final slots = <FlowInputSlot>[];
  final seen = <String>{};

  void add(String name, String kind, {String? hint}) {
    final n = name.trim();
    if (n.isEmpty) return;
    final key = '$kind::$n';
    if (!seen.add(key)) return;
    slots.add(FlowInputSlot(name: n, kind: kind, hint: hint));
  }

  final path = '${node['exact_path'] ?? node['path'] ?? ''}';
  for (final m in _pathParamRe.allMatches(path)) {
    add(m.group(1)!, 'path', hint: 'from path $path');
  }

  void fromMap(Object? raw, String kind) {
    if (raw is! Map) return;
    for (final k in raw.keys) {
      add('$k', kind, hint: '${raw[k]}');
    }
  }

  fromMap(node['bind_path'], 'path');
  fromMap(node['path_params'], 'path');
  fromMap(node['bind_query'], 'query');
  fromMap(node['query_override'], 'query');
  fromMap(node['body_override'], 'body');

  // Common market/payload keys when nothing declared yet.
  if (slots.isEmpty) {
    for (final name in const [
      'symbol',
      'symbols',
      'watchlistId',
      'ipoId',
      'schemeCode',
      'id',
    ]) {
      add(name, 'query');
    }
  }
  return slots;
}

/// One mapping row: previous response path → next input slot (variable name = slot.name).
class FieldMappingRow {
  FieldMappingRow({
    required this.responsePath,
    required this.inputName,
    required this.inputKind,
  });

  String responsePath;
  String inputName;
  String inputKind; // path | query | body
}

/// Merge mapping rows into capture (on prev) + bind maps (on next).
Map<String, dynamic> captureFromMappings(List<FieldMappingRow> rows) {
  final out = <String, dynamic>{};
  for (final r in rows) {
    final name = r.inputName.trim();
    final path = r.responsePath.trim();
    if (name.isEmpty || path.isEmpty) continue;
    out[name] = path;
  }
  return out;
}

Map<String, Map<String, dynamic>> bindsFromMappings(List<FieldMappingRow> rows) {
  final path = <String, dynamic>{};
  final query = <String, dynamic>{};
  final body = <String, dynamic>{};
  for (final r in rows) {
    final name = r.inputName.trim();
    if (name.isEmpty || r.responsePath.trim().isEmpty) continue;
    final token = '{{$name}}';
    switch (r.inputKind) {
      case 'path':
        path[name] = token;
        break;
      case 'body':
        body[name] = token;
        break;
      default:
        query[name] = token;
    }
  }
  return {
    if (path.isNotEmpty) 'bind_path': path,
    if (query.isNotEmpty) 'bind_query': query,
    if (body.isNotEmpty) 'body_override': body,
  };
}
