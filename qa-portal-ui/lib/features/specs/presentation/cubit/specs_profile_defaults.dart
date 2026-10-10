import 'specs_cubit.dart';

/// Bridge: Execute / Profiles → Specs OpenAPI defaults (env, service, dataset).
///
/// When SpecsCubit is mounted it registers as [liveCubit] and is updated
/// immediately. Otherwise values stay [pending] until Specs [boot] / ensure.
class SpecsProfileDefaults {
  String? environment;
  String? service;
  String? payloadVersion;
  bool pending = false;

  /// Soft ref to the open Specs workspace (not owned by get_it).
  SpecsCubit? liveCubit;

  static String? versionFromConfig(Map<String, dynamic> cfg) {
    for (final k in const [
      'payload_set_version',
      'payload_set',
      'data_version',
      'dataset_version',
    ]) {
      final v = cfg[k];
      if (v == null) continue;
      final s = '$v'.trim();
      if (s.isNotEmpty) return s;
    }
    return null;
  }

  void setFromConfig(Map<String, dynamic> cfg) {
    final env = '${cfg['environment'] ?? ''}'.trim();
    final svc = '${cfg['service'] ?? ''}'.trim();
    environment = env.isEmpty ? null : env;
    service = svc.isEmpty ? null : svc;
    payloadVersion = versionFromConfig(cfg);
    pending = true;
  }

  void clear() {
    environment = null;
    service = null;
    payloadVersion = null;
    pending = false;
  }

  /// Store defaults and push into live Specs when available.
  Future<void> pushFromConfig(Map<String, dynamic> cfg) async {
    setFromConfig(cfg);
    final cubit = liveCubit;
    if (cubit == null || cubit.isClosed) return;
    final env = environment;
    final svc = service;
    final ver = payloadVersion;
    clear();
    await cubit.applyProfileDefaults(
      environment: env,
      service: svc,
      payloadVersion: ver,
    );
  }
}
