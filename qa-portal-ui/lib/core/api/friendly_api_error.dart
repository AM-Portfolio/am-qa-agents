import '../config/portal_config.dart';
import '../config/portal_runtime.dart';
import '../di/injection.dart';

String _activeApiBase() {
  if (getIt.isRegistered<PortalRuntime>()) {
    return getIt<PortalRuntime>().apiBase;
  }
  if (getIt.isRegistered<PortalConfig>()) {
    return getIt<PortalConfig>().apiBase;
  }
  return '';
}

bool apiBaseLooksRemote(String base) {
  final b = base.toLowerCase();
  return b.contains('asrax.in') || b.contains('/qa');
}

/// Human-readable API errors for portal surfaces (Services, Flows, header).
String friendlyApiError(Object e, {String? missingRouteHint}) {
  final msg = e.toString();
  final base = _activeApiBase();
  if (msg.contains('connection error') ||
      msg.contains('XMLHttpRequest') ||
      msg.contains('Connection refused') ||
      msg.contains('Failed host lookup') ||
      msg.contains('SocketException')) {
    final where = base.isEmpty ? 'the API' : base;
    return 'Cannot reach $where — start qa-agent (python -m composition.main on :8150) '
        'or switch connection to Contabo dig / Preprod in Environments.';
  }
  if (msg.contains('404')) {
    final remoteHint = apiBaseLooksRemote(base)
        ? 'This Contabo dig/preprod qa-agent build is missing the route '
            '(overview/flows often 404). Use Datasets / OpenAPI catalog, '
            'or point connection at local :8150 for full Specs.'
        : null;
    final hint = missingRouteHint ??
        remoteHint ??
        'API route missing on this backend — point UI at local :8150 '
            '(npm run run:windows) or sync Contabo dig with latest qa-agent.';
    return hint;
  }
  if (msg.contains('401') || msg.contains('403')) {
    return 'Not authorized for this API — check operator session / credentials.';
  }
  if (msg.contains('DioException')) {
    // Strip Dio boilerplate; keep the useful clause when present.
    final status = RegExp(r'status code of (\d+)').firstMatch(msg)?.group(1);
    if (status != null) {
      return 'Request failed (HTTP $status). Retry or check qa-agent logs.';
    }
    return 'Request failed. Check API health and try again.';
  }
  return msg;
}
