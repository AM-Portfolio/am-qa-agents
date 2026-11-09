/// Named API origins the portal can switch at runtime (desktop Contabo dig config).
class ConnectionPreset {
  const ConnectionPreset({
    required this.id,
    required this.label,
    required this.apiBase,
  });

  final String id;
  final String label;
  final String apiBase;

  static const local = ConnectionPreset(
    id: 'local',
    label: 'Local',
    apiBase: 'http://localhost:8150',
  );

  static const contaboDig = ConnectionPreset(
    id: 'contabo-dig',
    label: 'Contabo dig',
    apiBase: 'https://am-dev.asrax.in/qa',
  );

  static const preprod = ConnectionPreset(
    id: 'preprod',
    label: 'Preprod',
    apiBase: 'https://am-preprod.asrax.in/qa',
  );

  static const all = <ConnectionPreset>[local, contaboDig, preprod];

  static ConnectionPreset? byId(String? id) {
    if (id == null || id.isEmpty) return null;
    for (final p in all) {
      if (p.id == id) return p;
    }
    return null;
  }

  static ConnectionPreset? byApiBase(String? base) {
    final b = (base ?? '').replaceAll(RegExp(r'/$'), '');
    if (b.isEmpty) return null;
    for (final p in all) {
      if (p.apiBase == b) return p;
    }
    return null;
  }
}
