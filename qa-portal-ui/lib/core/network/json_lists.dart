/// Normalize list payloads from api-load (`runs`, `configs`, `artifacts`, `apis`, `items`, …).
List<Map<String, dynamic>> mapList(
  dynamic data, {
  List<String> keys = const ['items', 'runs', 'configs', 'profiles', 'artifacts', 'apis', 'traces', 'payloads'],
}) {
  if (data is List) {
    return data
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }
  if (data is Map) {
    for (final k in keys) {
      final v = data[k];
      if (v is List) {
        return v
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList();
      }
    }
  }
  return [];
}

Map<String, dynamic> asMap(dynamic data) {
  if (data is Map) return Map<String, dynamic>.from(data);
  return {};
}

int asTotal(dynamic data, {int fallback = 0}) {
  if (data is Map) {
    final t = data['total'];
    if (t is int) return t;
    if (t is num) return t.toInt();
    final c = data['count'];
    if (c is int) return c;
    if (c is num) return c.toInt();
  }
  return fallback;
}
