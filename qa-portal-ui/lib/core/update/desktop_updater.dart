import '../config/portal_config.dart';
import 'desktop_updater_stub.dart'
    if (dart.library.io) 'desktop_updater_io.dart' as impl;

/// Thin Velopack update check (no-op on web / when Update.exe is absent).
Future<void> checkDesktopUpdates() => impl.checkDesktopUpdates();

/// Operator download page on the same qa-agent host (`/qa/download`).
String windowsDownloadPageUrl(PortalConfig cfg) {
  final api = cfg.apiBase.replaceAll(RegExp(r'/$'), '');
  if (api.startsWith('http://') || api.startsWith('https://')) {
    return '$api/download';
  }
  final root = cfg.rootPath.replaceAll(RegExp(r'/$'), '');
  if (root.isNotEmpty) {
    return '$root/download';
  }
  if (api.startsWith('/')) {
    return '$api/download';
  }
  return '/download';
}
