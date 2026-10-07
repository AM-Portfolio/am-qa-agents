import '../../../../core/config/portal_config.dart';
import '../../../../core/di/injection.dart';

String friendlyApiError(Object e) {
  final msg = e.toString();
  final base = getIt.isRegistered<PortalConfig>()
      ? getIt<PortalConfig>().apiBase
      : '';
  if (msg.contains('connection error') ||
      msg.contains('XMLHttpRequest') ||
      msg.contains('Connection refused') ||
      msg.contains('Failed host lookup')) {
    final where = base.isEmpty ? 'the API' : base;
    return 'Cannot reach $where — start qa-agent (python -m composition.main on :8150) '
        'or set API_BASE to a live /qa origin. Raw: $msg';
  }
  if (msg.contains('404')) {
    return 'API missing /api/flows — restart qa-agent with latest code on :8150. Raw: $msg';
  }
  return msg;
}

