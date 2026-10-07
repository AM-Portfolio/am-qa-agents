import 'package:am_design_system/am_design_system.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../../../core/network/json_lists.dart';
import '../../../../core/router/app_router.dart';
import '../../../execute/presentation/pages/execute_bar.dart';

/// QA operator shell — product [GlobalSidebar] + portal-specific destinations.
class OperatorShell extends StatelessWidget {
  const OperatorShell({super.key, required this.child});

  final Widget child;

  static const _nav = <(String route, String title, IconData icon)>[
    (AppRoutes.services, 'Services', Icons.hub_outlined),
    (AppRoutes.runs, 'Runs', Icons.play_circle_outline),
    (AppRoutes.profiles, 'Profiles', Icons.tune),
    (AppRoutes.specs, 'OpenAPI', Icons.api_outlined),
    (AppRoutes.flows, 'Flows', Icons.account_tree_outlined),
    (AppRoutes.uiFlows, 'UI flows', Icons.web_asset),
  ];

  static List<SidebarItem> get _items => [
        for (final d in _nav)
          SidebarItem(title: d.$2, icon: d.$3, route: d.$1),
      ];

  String _activeTitle(String location) {
    for (final d in _nav) {
      if (location.startsWith(d.$1)) return d.$2;
    }
    return _nav.first.$2;
  }

  void _onNavigate(BuildContext context, String title) {
    for (final d in _nav) {
      if (d.$2 == title) {
        context.go(d.$1);
        return;
      }
    }
  }

  Future<void> _showProfile(BuildContext context, _ShellState state) async {
    final op = state.operator;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Profile & Settings'),
        content: SizedBox(
          width: 360,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: CircleAvatar(
                  backgroundColor: AppColors.primary.withValues(alpha: 0.2),
                  child: Text(
                    () {
                      final name =
                          '${op?['display_name'] ?? op?['email'] ?? 'O'}';
                      return name.isEmpty ? 'O' : name[0].toUpperCase();
                    }(),
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                title: Text('${op?['display_name'] ?? 'Operator'}'),
                subtitle: Text('${op?['email'] ?? '—'}'),
              ),
              const Divider(),
              Text('User id: ${op?['user_id'] ?? '—'}'),
              const SizedBox(height: 8),
              Text(
                'QA portal uses SPT operator credentials from api-load (.env). '
                'Theme toggle is on the sidebar.',
                style: Theme.of(ctx).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return BlocProvider(
      create: (_) => _ShellCubit(getIt<Dio>())..refresh(),
      child: Scaffold(
        body: Row(
          children: [
            BlocBuilder<_ShellCubit, _ShellState>(
              builder: (context, shell) {
                return BlocBuilder<ThemeCubit, ThemeState>(
                  builder: (context, themeState) {
                    final op = shell.operator;
                    return GlobalSidebar(
                      activeNavItem: _activeTitle(location),
                      items: _items,
                      isDarkMode: themeState.isDarkMode || isDark,
                      userName: op?['display_name']?.toString() ?? 'Operator',
                      userEmail: op?['email']?.toString(),
                      onThemeToggle: () =>
                          context.read<ThemeCubit>().toggleTheme(),
                      onProfileTap: () => _showProfile(context, shell),
                      onLogout: () async {
                        await context.read<_ShellCubit>().clearCache();
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Operator caches cleared'),
                            ),
                          );
                        }
                      },
                      onNavigate: (title) => _onNavigate(context, title),
                    );
                  },
                );
              },
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Specs/Flows own their own run controls; hide global profile bar.
                  if (!location.startsWith(AppRoutes.specs) &&
                      !location.startsWith(AppRoutes.flows)) ...[
                    Material(
                      elevation: 0,
                      color: theme.colorScheme.surface,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          BlocBuilder<_ShellCubit, _ShellState>(
                            builder: (context, shell) {
                              return ExecuteBar(
                                apiOk: shell.apiOk && shell.k6Ok != false,
                                apiMessage: shell.k6Ok == false
                                    ? 'k6 missing'
                                    : shell.message,
                                onClearCache: () =>
                                    context.read<_ShellCubit>().clearCache(),
                              );
                            },
                          ),
                        ],
                      ),
                    ),
                    const Divider(height: 1),
                  ],
                  Expanded(child: child),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ShellState {
  const _ShellState({
    this.apiOk = false,
    this.k6Ok,
    this.grafanaUrl,
    this.minioUrl,
    this.operator,
    this.message,
  });

  final bool apiOk;
  final bool? k6Ok;
  final String? grafanaUrl;
  final String? minioUrl;
  final Map<String, dynamic>? operator;
  final String? message;

  _ShellState copyWith({
    bool? apiOk,
    bool? k6Ok,
    String? grafanaUrl,
    String? minioUrl,
    Map<String, dynamic>? operator,
    String? message,
  }) {
    return _ShellState(
      apiOk: apiOk ?? this.apiOk,
      k6Ok: k6Ok ?? this.k6Ok,
      grafanaUrl: grafanaUrl ?? this.grafanaUrl,
      minioUrl: minioUrl ?? this.minioUrl,
      operator: operator ?? this.operator,
      message: message,
    );
  }
}

class _ShellCubit extends Cubit<_ShellState> {
  _ShellCubit(this._dio) : super(const _ShellState());

  final Dio _dio;

  Future<void> refresh() async {
    try {
      final res = await _dio.get<dynamic>('/api/platform/health');
      final data = asMap(res.data);
      final op = data['operator'];
      emit(
        _ShellState(
          apiOk: true,
          k6Ok: data['k6_binary'] == true,
          grafanaUrl: data['grafana_url']?.toString(),
          minioUrl: data['minio_console_url']?.toString() ??
              (data['minio'] is Map
                  ? (data['minio'] as Map)['console_url']?.toString()
                  : null),
          operator: op is Map ? Map<String, dynamic>.from(op) : null,
          message: data['k6_binary'] == true ? null : 'k6 binary missing on agent',
        ),
      );
    } catch (e) {
      emit(
        _ShellState(
          apiOk: false,
          k6Ok: false,
          message: e.toString(),
          operator: state.operator,
          grafanaUrl: state.grafanaUrl,
          minioUrl: state.minioUrl,
        ),
      );
    }
  }

  Future<void> clearCache() async {
    try {
      await _dio.post<dynamic>('/api/platform/clear-cache');
      emit(state.copyWith(message: 'Cache cleared'));
      await refresh();
    } catch (e) {
      emit(state.copyWith(message: e.toString()));
    }
  }
}
