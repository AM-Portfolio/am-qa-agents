/// Runtime config for the QA operator portal.
class PortalConfig {
  const PortalConfig({
    required this.apiBase,
    this.rootPath = '',
  });

  /// Absolute or same-origin API prefix, e.g. `http://localhost:8150` or `/spt-poc`.
  final String apiBase;

  /// Traefik / reverse-proxy prefix (e.g. `/spt-poc`) when served from api-load.
  final String rootPath;

  factory PortalConfig.fromEnvironment() {
    const api = String.fromEnvironment('API_BASE', defaultValue: '');
    const root = String.fromEnvironment('ROOT_PATH', defaultValue: '');
    if (api.isNotEmpty) {
      return PortalConfig(apiBase: api.replaceAll(RegExp(r'/$'), ''), rootPath: root);
    }
    // Same-origin when hosted under api-load (use ROOT_PATH if set).
    final prefix = root.replaceAll(RegExp(r'/$'), '');
    return PortalConfig(apiBase: prefix.isEmpty ? '' : prefix, rootPath: prefix);
  }
}
