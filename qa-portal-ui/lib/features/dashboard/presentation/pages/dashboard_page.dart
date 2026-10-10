import 'package:am_design_system/am_design_system.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/di/injection.dart';
import '../../../../core/router/app_router.dart';
import '../../../runs/data/runs_repository.dart';
import '../../../services/data/services_repository.dart';
import '../../../specs/data/specs_repository.dart';

/// SPT / QA operator home — platform health, dashboards, and fleet metrics.
class DashboardPage extends StatelessWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => DashboardCubit(
        getIt<SpecsRepository>(),
        getIt<RunsRepository>(),
        getIt<ServicesRepository>(),
      )..load(),
      child: const _DashboardView(),
    );
  }
}

class DashboardState extends Equatable {
  const DashboardState({
    this.loading = true,
    this.health = const {},
    this.services = const [],
    this.serviceLabels = const {},
    this.recentRuns = const [],
    this.runsTotal = 0,
    this.error,
  });

  final bool loading;
  final Map<String, dynamic> health;
  final List<String> services;
  final Map<String, String> serviceLabels;
  final List<Map<String, dynamic>> recentRuns;
  final int runsTotal;
  final String? error;

  DashboardState copyWith({
    bool? loading,
    Map<String, dynamic>? health,
    List<String>? services,
    Map<String, String>? serviceLabels,
    List<Map<String, dynamic>>? recentRuns,
    int? runsTotal,
    String? error,
    bool clearError = false,
  }) {
    return DashboardState(
      loading: loading ?? this.loading,
      health: health ?? this.health,
      services: services ?? this.services,
      serviceLabels: serviceLabels ?? this.serviceLabels,
      recentRuns: recentRuns ?? this.recentRuns,
      runsTotal: runsTotal ?? this.runsTotal,
      error: clearError ? null : (error ?? this.error),
    );
  }

  @override
  List<Object?> get props =>
      [loading, health, services, serviceLabels, recentRuns, runsTotal, error];
}

class DashboardCubit extends Cubit<DashboardState> {
  DashboardCubit(this._specs, this._runs, this._services)
      : super(const DashboardState());

  final SpecsRepository _specs;
  final RunsRepository _runs;
  final ServicesRepository _services;

  Future<void> load() async {
    emit(state.copyWith(loading: true, clearError: true));
    try {
      final health = await _specs.platformHealth();
      final catalog = await _services.listServices();
      final runs = await _runs.listRuns(limit: 12, offset: 0);
      emit(
        state.copyWith(
          loading: false,
          health: health,
          services: catalog.ids,
          serviceLabels: catalog.labels,
          recentRuns: runs.runs,
          runsTotal: runs.total,
          clearError: true,
        ),
      );
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }
}

class _DashboardView extends StatelessWidget {
  const _DashboardView();

  Future<void> _open(String? url) async {
    if (url == null || url.isEmpty) return;
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<DashboardCubit, DashboardState>(
      builder: (context, state) {
        if (state.loading && state.health.isEmpty) {
          return const Center(child: CircularProgressIndicator());
        }
        final h = state.health;
        final status = '${h['status'] ?? (state.error == null ? 'ok' : 'down')}';
        final k6 = h['k6_binary'] == true;
        final grafana = h['grafana_url']?.toString();
        final minio = h['minio_console_url']?.toString() ??
            (h['minio'] is Map
                ? (h['minio'] as Map)['console_url']?.toString()
                : null);
        final qaPortal = h['qa_portal_url']?.toString() ??
            h['portal_url']?.toString();
        final prometheus = h['prometheus_url']?.toString();

        final passed = state.recentRuns
            .where((r) => r['passed'] == true || '${r['status']}' == 'passed')
            .length;
        final failed = state.recentRuns
            .where(
              (r) =>
                  r['passed'] == false ||
                  '${r['status']}' == 'failed' ||
                  '${r['status']}' == 'error',
            )
            .length;
        final running = state.recentRuns
            .where(
              (r) =>
                  '${r['status']}' == 'running' ||
                  '${r['status']}' == 'pending',
            )
            .length;

        return Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
          child: ListView(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'QA / SPT Dashboard',
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ),
                  IconButton(
                    tooltip: 'Refresh',
                    onPressed: () => context.read<DashboardCubit>().load(),
                    icon: state.loading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.refresh),
                  ),
                ],
              ),
              Text(
                'Platform health, observability links, and recent QA activity.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppColors.textSecondaryDark,
                    ),
              ),
              if (state.error != null) ...[
                const SizedBox(height: 8),
                Text(
                  state.error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 16),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  _MetricCard(
                    label: 'SPT API',
                    value: status.toUpperCase(),
                    icon: Icons.health_and_safety_outlined,
                    tone: status.toLowerCase() == 'ok' ||
                            status.toLowerCase() == 'healthy'
                        ? _Tone.ok
                        : _Tone.warn,
                  ),
                  _MetricCard(
                    label: 'k6 binary',
                    value: k6 ? 'Ready' : 'Missing',
                    icon: Icons.speed_outlined,
                    tone: k6 ? _Tone.ok : _Tone.warn,
                  ),
                  _MetricCard(
                    label: 'Services',
                    value: '${state.services.length}',
                    icon: Icons.hub_outlined,
                    tone: _Tone.neutral,
                  ),
                  _MetricCard(
                    label: 'Runs (total)',
                    value: '${state.runsTotal}',
                    icon: Icons.play_circle_outline,
                    tone: _Tone.neutral,
                  ),
                  _MetricCard(
                    label: 'Recent pass',
                    value: '$passed',
                    icon: Icons.check_circle_outline,
                    tone: _Tone.ok,
                  ),
                  _MetricCard(
                    label: 'Recent fail',
                    value: '$failed',
                    icon: Icons.error_outline,
                    tone: failed > 0 ? _Tone.warn : _Tone.neutral,
                  ),
                  _MetricCard(
                    label: 'Running',
                    value: '$running',
                    icon: Icons.timelapse,
                    tone: running > 0 ? _Tone.info : _Tone.neutral,
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Text(
                'Dashboards & consoles',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _DashLink(
                    label: 'Grafana',
                    icon: Icons.insights_outlined,
                    enabled: grafana != null && grafana.isNotEmpty,
                    onTap: () => _open(grafana),
                  ),
                  _DashLink(
                    label: 'Prometheus',
                    icon: Icons.timeline_outlined,
                    enabled: prometheus != null && prometheus.isNotEmpty,
                    onTap: () => _open(prometheus),
                  ),
                  _DashLink(
                    label: 'MinIO',
                    icon: Icons.folder_outlined,
                    enabled: minio != null && minio.isNotEmpty,
                    onTap: () => _open(minio),
                  ),
                  _DashLink(
                    label: 'QA portal (cluster)',
                    icon: Icons.open_in_new,
                    enabled: qaPortal != null && qaPortal.isNotEmpty,
                    onTap: () => _open(qaPortal),
                  ),
                  _DashLink(
                    label: 'OpenAPI',
                    icon: Icons.api_outlined,
                    enabled: true,
                    onTap: () => context.go(AppRoutes.specs),
                  ),
                  _DashLink(
                    label: 'Runs',
                    icon: Icons.play_circle_outline,
                    enabled: true,
                    onTap: () => context.go(AppRoutes.runs),
                  ),
                  _DashLink(
                    label: 'Service catalog',
                    icon: Icons.hub_outlined,
                    enabled: true,
                    onTap: () => context.go(AppRoutes.services),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Text(
                'Catalog services',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              const SizedBox(height: 8),
              if (state.services.isEmpty)
                Text(
                  'No services in catalog yet.',
                  style: Theme.of(context).textTheme.bodySmall,
                )
              else
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final id in state.services.take(24))
                      ActionChip(
                        visualDensity: VisualDensity.compact,
                        label: Text(
                          state.serviceLabels[id] ?? id,
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                        onPressed: () => context.go('${AppRoutes.services}/$id'),
                      ),
                    if (state.services.length > 24)
                      ActionChip(
                        visualDensity: VisualDensity.compact,
                        label: Text('+${state.services.length - 24} more'),
                        onPressed: () => context.go(AppRoutes.services),
                      ),
                  ],
                ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Text(
                    'Recent runs',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const Spacer(),
                  TextButton(
                    onPressed: () => context.go(AppRoutes.runs),
                    child: const Text('View all'),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              GlassCard(
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    if (state.recentRuns.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(16),
                        child: Text('No recent runs.'),
                      )
                    else
                      for (final r in state.recentRuns)
                        ListTile(
                          dense: true,
                          leading: Icon(
                            _runIcon(r),
                            size: 18,
                            color: _runColor(context, r),
                          ),
                          title: Text(
                            '${r['id'] ?? ''}'.length > 10
                                ? '${'${r['id']}'.substring(0, 8)}…'
                                : '${r['id'] ?? ''}',
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          subtitle: Text(
                            '${r['service'] ?? '—'} · ${r['test_type'] ?? ''} · '
                            '${r['status'] ?? ''}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          trailing: Text(
                            '${r['environment'] ?? ''}',
                            style: Theme.of(context).textTheme.labelSmall,
                          ),
                          onTap: () {
                            final id = '${r['id'] ?? ''}';
                            if (id.isNotEmpty) {
                              context.go('${AppRoutes.runs}/$id');
                            }
                          },
                        ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  IconData _runIcon(Map<String, dynamic> r) {
    final s = '${r['status'] ?? ''}'.toLowerCase();
    if (r['passed'] == true || s == 'passed' || s == 'completed') {
      return Icons.check_circle;
    }
    if (s == 'running' || s == 'pending') return Icons.timelapse;
    if (s == 'failed' || s == 'error' || r['passed'] == false) {
      return Icons.error;
    }
    return Icons.circle_outlined;
  }

  Color _runColor(BuildContext context, Map<String, dynamic> r) {
    final s = '${r['status'] ?? ''}'.toLowerCase();
    if (r['passed'] == true || s == 'passed' || s == 'completed') {
      return const Color(0xFF22C55E);
    }
    if (s == 'running' || s == 'pending') return AppColors.primary;
    if (s == 'failed' || s == 'error' || r['passed'] == false) {
      return Theme.of(context).colorScheme.error;
    }
    return Theme.of(context).colorScheme.outline;
  }
}

enum _Tone { ok, warn, info, neutral }

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.tone,
  });

  final String label;
  final String value;
  final IconData icon;
  final _Tone tone;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final color = switch (tone) {
      _Tone.ok => const Color(0xFF22C55E),
      _Tone.warn => Colors.amber.shade700,
      _Tone.info => AppColors.primary,
      _Tone.neutral => cs.onSurfaceVariant,
    };
    return SizedBox(
      width: 148,
      child: GlassCard(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 18, color: color),
            const SizedBox(height: 8),
            Text(
              value,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                    color: color,
                  ),
            ),
            Text(
              label,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.textSecondaryDark,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DashLink extends StatelessWidget {
  const _DashLink({
    required this.label,
    required this.icon,
    required this.enabled,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: enabled ? onTap : null,
      icon: Icon(icon, size: 16),
      label: Text(label),
    );
  }
}
