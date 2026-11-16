import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import 'app.dart';
import 'core/di/injection.dart';
import 'core/utils/url_strategy_noop.dart'
    if (dart.library.html) 'package:flutter_web_plugins/url_strategy.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (kIsWeb) {
    usePathUrlStrategy();
  }
  await configureDependencies();
  runApp(const QaPortalApp());
}
