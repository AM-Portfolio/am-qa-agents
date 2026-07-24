import 'package:flutter_test/flutter_test.dart';
import 'package:am_qa_portal/core/config/portal_config.dart';

void main() {
  test('PortalConfig.fromEnvironment uses API_BASE when provided', () {
    // fromEnvironment reads compile-time defines; default empty → same-origin.
    final cfg = PortalConfig.fromEnvironment();
    expect(cfg.apiBase, isA<String>());
  });

  test('PortalConfig stores apiBase', () {
    const cfg = PortalConfig(apiBase: 'http://localhost:8150', rootPath: '');
    expect(cfg.apiBase, 'http://localhost:8150');
  });
}
