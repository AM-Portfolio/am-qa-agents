import 'package:flutter/foundation.dart';
import 'package:go_router/go_router.dart';

import '../../features/datasets/presentation/pages/datasets_page.dart';
import '../../features/profiles/presentation/pages/profiles_page.dart';
import '../../features/runs/presentation/pages/run_detail_page.dart';
import '../../features/runs/presentation/pages/runs_page.dart';
import '../../features/services/presentation/pages/services_page.dart';
import '../../features/shell/presentation/pages/operator_shell.dart';
import '../../features/specs/presentation/pages/specs_page.dart';
import '../../features/flows/presentation/pages/flows_page.dart';
import '../../features/ui_flows/presentation/pages/ui_flows_page.dart';

abstract final class AppRoutes {
  static const services = '/services';
  static const runs = '/runs';
  static const profiles = '/profiles';
  static const specs = '/specs';
  static const datasets = '/datasets';
  static const flows = '/flows';
  static const uiFlows = '/ui-flows';
}

GoRouter createPortalRouter() {
  return GoRouter(
    initialLocation: AppRoutes.services,
    redirect: (context, state) {
      final loc = state.uri.path;
      if (loc.isEmpty || loc == '/') {
        return AppRoutes.services;
      }
      // Prefer go_router URI (works on desktop). On web also honor legacy
      // deep links on the browser location (?run= / ?config=).
      final qp = <String, String>{
        ...state.uri.queryParameters,
        if (kIsWeb) ...Uri.base.queryParameters,
      };

      final run = qp['run'];
      if (run != null &&
          run.isNotEmpty &&
          state.matchedLocation == AppRoutes.runs) {
        return '/runs/$run';
      }
      final config = qp['config'];
      if (config != null &&
          config.isNotEmpty &&
          state.matchedLocation == AppRoutes.runs) {
        return '/profiles?config=$config';
      }
      return null;
    },
    routes: [
      ShellRoute(
        builder: (context, state, child) => OperatorShell(child: child),
        routes: [
          GoRoute(
            path: AppRoutes.services,
            pageBuilder: (context, state) => NoTransitionPage(
              child: ServicesPage(
                initialService: state.uri.queryParameters['service'],
              ),
            ),
            routes: [
              GoRoute(
                path: ':serviceKey',
                pageBuilder: (context, state) => NoTransitionPage(
                  child: ServicesPage(
                    initialService: state.pathParameters['serviceKey'],
                  ),
                ),
              ),
            ],
          ),
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
            path: AppRoutes.datasets,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: DatasetsPage(),
            ),
          ),
          GoRoute(
            path: AppRoutes.flows,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: FlowsPage(),
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
