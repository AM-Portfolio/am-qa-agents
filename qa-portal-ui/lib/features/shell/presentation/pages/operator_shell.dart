import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../../../execute/presentation/pages/execute_bar.dart';

/// QA operator shell — product design-system look, portal-specific nav (not am_app modules).
class OperatorShell extends StatelessWidget {
  const OperatorShell({super.key, required this.child});

  final Widget child;

  static const _destinations = [
    (AppRoutes.runs, 'Runs', Icons.play_circle_outline),
    (AppRoutes.profiles, 'Profiles', Icons.tune),
    (AppRoutes.specs, 'OpenAPI', Icons.api_outlined),
    (AppRoutes.uiFlows, 'UI flows', Icons.web_asset),
  ];

  int _indexForLocation(String location) {
    for (var i = 0; i < _destinations.length; i++) {
      if (location.startsWith(_destinations[i].$1)) return i;
    }
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    final selected = _indexForLocation(location);
    final theme = Theme.of(context);

    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: selected,
            onDestinationSelected: (i) => context.go(_destinations[i].$1),
            labelType: NavigationRailLabelType.all,
            backgroundColor: theme.colorScheme.surface,
            leading: Padding(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Column(
                children: [
                  Icon(Icons.science_outlined, color: AppColors.primary, size: 28),
                  const SizedBox(height: 8),
                  Text(
                    'QA',
                    style: theme.textTheme.labelLarge?.copyWith(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
            trailing: Expanded(
              child: Align(
                alignment: Alignment.bottomCenter,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: BlocBuilder<ThemeCubit, ThemeState>(
                    builder: (context, state) {
                      final isDark = state.isDarkMode;
                      return IconButton(
                        tooltip: isDark ? 'Light theme' : 'Dark theme',
                        onPressed: () => context.read<ThemeCubit>().toggleTheme(),
                        icon: Icon(isDark ? Icons.light_mode : Icons.dark_mode),
                      );
                    },
                  ),
                ),
              ),
            ),
            destinations: [
              for (final d in _destinations)
                NavigationRailDestination(
                  icon: Icon(d.$3),
                  label: Text(d.$2),
                ),
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Material(
                  elevation: 0,
                  color: theme.colorScheme.surface,
                  child: const ExecuteBar(),
                ),
                const Divider(height: 1),
                Expanded(child: child),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
