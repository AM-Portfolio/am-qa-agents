import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';

import '../auth/auth_service.dart';
import '../../features/auth/presentation/pages/callback_page.dart';
import '../../features/auth/presentation/pages/portal_login_page.dart';
import '../../features/profiles/presentation/pages/profiles_page.dart';
import '../../features/runs/presentation/pages/run_detail_page.dart';
import '../../features/runs/presentation/pages/runs_page.dart';
import '../../features/shell/presentation/pages/operator_shell.dart';
import '../../features/specs/presentation/pages/specs_page.dart';
import '../../features/ui_flows/presentation/pages/ui_flows_page.dart';

abstract final class AppRoutes {
  static const login = '/login';
  static const runs = '/runs';
  static const profiles = '/profiles';
  static const specs = '/specs';
  static const uiFlows = '/ui-flows';
  static const callback = '/callback';
}

String _portalLaunchLocation() {
  if (Uri.base.queryParameters['qa_sso'] == '1') {
    return '${AppRoutes.login}?qa_sso=1';
  }
  // Full-page SSO return lands on /callback?code=... — must not start at /ui-flows
  // or GoRouter drops the query and the callback page reports "Missing authorization code".
  final path = Uri.base.path;
  if (path == AppRoutes.callback || path.endsWith('/callback')) {
    return Uri.base.hasQuery
        ? '${AppRoutes.callback}?${Uri.base.query}'
        : AppRoutes.callback;
  }
  if (path == AppRoutes.login || path.endsWith('/login')) {
    return Uri.base.hasQuery
        ? '${AppRoutes.login}?${Uri.base.query}'
        : AppRoutes.login;
  }
  return AppRoutes.uiFlows;
}

GoRouter createPortalRouter() {
  return GoRouter(
    initialLocation: _portalLaunchLocation(),
    redirect: (context, state) {
      if (state.matchedLocation == AppRoutes.callback ||
          state.uri.path == AppRoutes.callback ||
          Uri.base.path.endsWith('/callback')) {
        return null;
      }

      final auth = GetIt.instance<QaAuthService>();
      final isAuth = auth.isAuthenticated;

      if (state.matchedLocation == AppRoutes.login) {
        return isAuth ? AppRoutes.uiFlows : null;
      }

      if (!isAuth) {
        return AppRoutes.login;
      }

      if (state.matchedLocation == '/' || state.matchedLocation.isEmpty) {
        return AppRoutes.uiFlows;
      }
      final base = Uri.base.queryParameters;
      final run = base['run'];
      if (run != null &&
          run.isNotEmpty &&
          state.matchedLocation == AppRoutes.runs) {
        return '/runs/$run';
      }
      final config = base['config'];
      if (config != null &&
          config.isNotEmpty &&
          state.matchedLocation == AppRoutes.runs) {
        return '/profiles?config=$config';
      }
      return null;
    },
    routes: [
      GoRoute(
        path: AppRoutes.login,
        builder: (context, state) => const PortalLoginPage(),
      ),
      GoRoute(
        path: AppRoutes.callback,
        builder: (context, state) {
          final uri = Uri.base;
          final qp = {...uri.queryParameters, ...state.uri.queryParameters};
          // Central Login may send OAuth `code` or legacy `token` (am_* direct).
          final code = qp['code'] ?? qp['token'];
          final returnState = qp['state'];
          return CallbackPage(
            code: code,
            state: returnState,
            email: qp['email'],
          );
        },
      ),
      ShellRoute(
        builder: (context, state, child) => OperatorShell(child: child),
        routes: [
          GoRoute(
            path: AppRoutes.runs,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: RunsPage(),
            ),
            routes: [
              GoRoute(
                path: ':id',
                builder: (context, state) => RunDetailPage(
                  runId: state.pathParameters['id']!,
                ),
              ),
            ],
          ),
          GoRoute(
            path: AppRoutes.profiles,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: ProfilesPage(),
            ),
          ),
          GoRoute(
            path: AppRoutes.specs,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: SpecsPage(),
            ),
          ),
          GoRoute(
            path: AppRoutes.uiFlows,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: UiFlowsPage(),
            ),
          ),
        ],
      ),
    ],
  );
}
