import 'package:flutter/foundation.dart';

/// Runtime config for the QA operator portal.
class PortalConfig {
  const PortalConfig({
    required this.apiBase,
    this.rootPath = '',
  });

  /// Absolute or same-origin API prefix, e.g. `http://localhost:8150` or `/qa`.
  final String apiBase;

  /// Traefik / reverse-proxy prefix (e.g. `/qa`) when served from api-load.
  final String rootPath;

  /// Default API for desktop builds when `API_BASE` is not passed.
  static const desktopDefaultApiBase = 'http://localhost:8150';

  factory PortalConfig.fromEnvironment() {
    const api = String.fromEnvironment('API_BASE', defaultValue: '');
    const root = String.fromEnvironment('ROOT_PATH', defaultValue: '');
    if (api.isNotEmpty) {
      return PortalConfig(
        apiBase: api.replaceAll(RegExp(r'/$'), ''),
        rootPath: root,
      );
    }

    // Desktop has no same-origin host — fall back to local qa-agent.
    if (!kIsWeb) {
      return const PortalConfig(apiBase: desktopDefaultApiBase);
    }

    // Same-origin when hosted under api-load (use ROOT_PATH if set).
    var prefix = root.replaceAll(RegExp(r'/$'), '');
    if (prefix.isEmpty) {
      // Infer from browser path: /spt-poc/ui/... → /spt-poc
      final path = Uri.base.path;
      final m = RegExp(r'^(/[^/]+)(/ui(?:/|$))').firstMatch(path);
      if (m != null) {
        prefix = m.group(1)!;
      }
    }
    return PortalConfig(apiBase: prefix, rootPath: prefix);
  }
}
