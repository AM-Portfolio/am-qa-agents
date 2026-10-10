// Shared payload-set lookup helpers (Specs Test + Run Report Try).

Map<String, dynamic>? findSetEntry(
  Map apis, {
  required String apiId,
  String? method,
  String? path,
}) {
  dynamic entry = apis[apiId] ?? apis[apiId.replaceAll('.', '_')];
  if (entry is Map) return Map<String, dynamic>.from(entry);
  final lower = apiId.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
  for (final e in apis.entries) {
    final k = '${e.key}'.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
    if (k == lower && e.value is Map) {
      return Map<String, dynamic>.from(e.value as Map);
    }
  }
  final m = (method ?? '').toUpperCase();
  final p = (path ?? '').trim();
  if (m.isEmpty || p.isEmpty) return null;
  for (final e in apis.entries) {
    if (e.value is! Map) continue;
    final row = Map<String, dynamic>.from(e.value as Map);
    final req = row['request'] is Map
        ? Map<String, dynamic>.from(row['request'] as Map)
        : row;
    final rm = '${req['method'] ?? ''}'.toUpperCase();
    final rp = '${req['path'] ?? ''}'.trim();
    if (rm == m && (rp == p || rp.endsWith(p) || p.endsWith(rp))) {
      return row;
    }
  }
  return null;
}
