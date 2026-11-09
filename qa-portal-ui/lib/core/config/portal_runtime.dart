import 'package:dio/dio.dart';

import '../di/injection.dart';
import 'connection_presets.dart';
import 'portal_config.dart';

/// Mutable API base used after bake-time [PortalConfig] (workspace connection switch).
class PortalRuntime {
  PortalRuntime(this._apiBase);

  String _apiBase;

  String get apiBase => _apiBase;

  void setApiBase(String base) {
    final next = base.replaceAll(RegExp(r'/$'), '');
    if (next.isEmpty || next == _apiBase) return;
    _apiBase = next;
    if (getIt.isRegistered<Dio>()) {
      getIt<Dio>().options.baseUrl = next;
    }
  }

  void applyPreset(ConnectionPreset preset) => setApiBase(preset.apiBase);

  factory PortalRuntime.fromConfig(PortalConfig cfg) =>
      PortalRuntime(cfg.apiBase);
}
