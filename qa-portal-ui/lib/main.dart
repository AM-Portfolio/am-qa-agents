import 'package:flutter/material.dart';

import 'app.dart';
import 'core/di/injection.dart';
import 'core/update/desktop_updater.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await configureDependencies();
  // Fire-and-forget; no-op on web / unpackaged debug builds.
  // ignore: unawaited_futures
  checkDesktopUpdates();
  runApp(const QaPortalApp());
}
