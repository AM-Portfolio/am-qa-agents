import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;

/// Default Velopack feed — GitHub Releases assets for the latest qa-portal tag.
const _defaultFeedUrl =
    'https://github.com/AM-Portfolio/am-qa-agents/releases/latest/download';

/// Locate Velopack `Update.exe` next to the stub or one level above `current/`.
File? _findUpdateExe() {
  final exe = File(Platform.resolvedExecutable);
  final dir = exe.parent;
  final candidates = <File>[
    File(p.join(dir.path, 'Update.exe')),
    File(p.join(dir.parent.path, 'Update.exe')),
  ];
  for (final f in candidates) {
    if (f.existsSync()) return f;
  }
  return null;
}

/// Best-effort update check via Velopack Update.exe (packed releases only).
///
/// Debug / unpackaged builds have no Update.exe — this is a silent no-op.
Future<void> checkDesktopUpdates() async {
  if (kIsWeb || !Platform.isWindows) return;

  const feed = String.fromEnvironment(
    'VELOPACK_URL',
    defaultValue: _defaultFeedUrl,
  );
  if (feed.isEmpty) return;

  final updateExe = _findUpdateExe();
  if (updateExe == null) {
    debugPrint('Velopack Update.exe not found — skip update check');
    return;
  }

  try {
    final check = await Process.run(
      updateExe.path,
      ['check', '--url', feed],
      workingDirectory: updateExe.parent.path,
    );
    if (check.exitCode != 0) {
      debugPrint(
        'Velopack check exit ${check.exitCode}: ${check.stderr}'.trim(),
      );
      return;
    }
    final out = '${check.stdout}'.trim();
    if (out.isEmpty ||
        out.toLowerCase().contains('no update') ||
        out.toLowerCase().contains('up to date')) {
      return;
    }

    debugPrint('Velopack update available — downloading');
    final download = await Process.run(
      updateExe.path,
      ['download', '--url', feed],
      workingDirectory: updateExe.parent.path,
    );
    if (download.exitCode != 0) {
      debugPrint(
        'Velopack download exit ${download.exitCode}: ${download.stderr}'
            .trim(),
      );
      return;
    }

    await Process.start(
      updateExe.path,
      ['apply', '--restart', '--wait', '$pid'],
      workingDirectory: updateExe.parent.path,
      mode: ProcessStartMode.detached,
    );
  } catch (e, st) {
    debugPrint('Velopack update check failed: $e\n$st');
  }
}
