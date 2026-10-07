import 'package:am_design_system/am_design_system.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../../../core/network/json_lists.dart';
import '../../../../core/router/app_router.dart';
import '../../../execute/data/execute_repository.dart';
import '../../data/services_repository.dart';
import '../widgets/coverage_board.dart';

class ServicesPage extends StatelessWidget {
  const ServicesPage({super.key, this.initialService});

  final String? initialService;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => ServicesCubit(getIt<ServicesRepository>())
        ..boot(initialService: initialService),
      child: const _ServicesView(),
    );
  }
}

class ServicesState extends Equatable {
  const ServicesState({
    this.loading = false,
    this.overviewLoading = false,
    this.services = const [],
    this.serviceLabels = const {},
    this.railQuery = '',
    this.selectedService,
    this.environment = 'dev',
    this.overview,
    this.runStatusFilter = '',
    this.runQuery = '',
    this.error,
  });

  final bool loading;
  final bool overviewLoading;
  final List<String> services;
  final Map<String, String> serviceLabels;
  final String railQuery;
  final String? selectedService;
  final String environment;
  final Map<String, dynamic>? overview;
  final String runStatusFilter;
  final String runQuery;
  final String? error;

  String labelFor(String id) => serviceLabels[id] ?? id;

  List<String> get filteredServices {
    final q = railQuery.trim().toLowerCase();
    if (q.isEmpty) return services;
    return services
        .where(
          (id) =>
              id.toLowerCase().contains(q) ||
              labelFor(id).toLowerCase().contains(q),
        )
        .toList();
  }

  List<Map<String, dynamic>> get filteredRuns {
    final raw = overview?['runs'];
    final runs = mapList(raw);
    final status = runStatusFilter.trim().toLowerCase();
    final q = runQuery.trim().toLowerCase();
    return runs.where((r) {
      if (status.isNotEmpty &&
          '${r['status'] ?? ''}'.toLowerCase() != status) {
        return false;
      }
      if (q.isEmpty) return true;
      final hay =
          '${r['id']} ${r['triggered_by']} ${r['config_name']} ${r['status']}'
              .toLowerCase();
      return hay.contains(q);
    }).toList();
  }

  ServicesState copyWith({
    bool? loading,
    bool? overviewLoading,
    List<String>? services,
    Map<String, String>? serviceLabels,
    String? railQuery,
    String? selectedService,
    bool clearSelected = false,
    String? environment,
    Map<String, dynamic>? overview,
    bool clearOverview = false,
    String? runStatusFilter,
    String? runQuery,
    String? error,
    bool clearError = false,
  }) {
    return ServicesState(
      loading: loading ?? this.loading,
      overviewLoading: overviewLoading ?? this.overviewLoading,
      services: services ?? this.services,
      serviceLabels: serviceLabels ?? this.serviceLabels,
      railQuery: railQuery ?? this.railQuery,
      selectedService:
          clearSelected ? null : (selectedService ?? this.selectedService),
      environment: environment ?? this.environment,
      overview: clearOverview ? null : (overview ?? this.overview),
      runStatusFilter: runStatusFilter ?? this.runStatusFilter,
      runQuery: runQuery ?? this.runQuery,
      error: clearError ? null : (error ?? this.error),
    );
  }

  @override
  List<Object?> get props => [
        loading,
        overviewLoading,
        services,
        serviceLabels,
        railQuery,
        selectedService,
        environment,
        overview,
        runStatusFilter,
        runQuery,
        error,
      ];
}

class ServicesCubit extends Cubit<ServicesState> {
  ServicesCubit(this._repo) : super(const ServicesState());

  final ServicesRepository _repo;

  Future<void> boot({String? initialService}) async {
    emit(state.copyWith(loading: true, clearError: true));
    try {
      final listed = await _repo.listServices();
      final pick = (initialService != null &&
              listed.ids.contains(initialService))
          ? initialService
          : (listed.ids.isNotEmpty ? listed.ids.first : null);
      emit(
        state.copyWith(
          loading: false,
          services: listed.ids,
          serviceLabels: listed.labels,
          selectedService: pick,
        ),
      );
      if (pick != null) {
        await selectService(pick);
      }
    } catch (e) {
      emit(state.copyWith(loading: false, error: '$e'));
    }
  }

  void setRailQuery(String q) => emit(state.copyWith(railQuery: q));

  void setRunStatusFilter(String v) =>
      emit(state.copyWith(runStatusFilter: v));

  void setRunQuery(String q) => emit(state.copyWith(runQuery: q));

  Future<void> setEnvironment(String env) async {
    emit(state.copyWith(environment: env));
    final svc = state.selectedService;
    if (svc != null) await selectService(svc);
  }

  Future<void> selectService(String serviceId) async {
    emit(
      state.copyWith(
        selectedService: serviceId,
        overviewLoading: true,
        clearError: true,
        clearOverview: true,
        runStatusFilter: '',
        runQuery: '',
      ),
    );
    try {
      final ov = await _repo.overview(
        serviceId,
        environment: state.environment,
      );
      emit(state.copyWith(overviewLoading: false, overview: ov));
    } catch (e) {
      emit(state.copyWith(overviewLoading: false, error: '$e'));
    }
  }

  Future<void> refresh() async {
    final svc = state.selectedService;
    if (svc == null) {
      await boot();
      return;
    }
    await selectService(svc);
  }
}

class _ServicesView extends StatelessWidget {
  const _ServicesView();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            width: 260,
            child: GlassCard(
              padding: const EdgeInsets.all(12),
              child: BlocBuilder<ServicesCubit, ServicesState>(
                builder: (context, state) {
                  final cubit = context.read<ServicesCubit>();
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        'Services',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        decoration: const InputDecoration(
                          isDense: true,
                          hintText: 'Search catalog…',
                          prefixIcon: Icon(Icons.search, size: 18),
                        ),
                        onChanged: cubit.setRailQuery,
                      ),
                      const SizedBox(height: 8),
                      DropdownButtonFormField<String>(
                        key: ValueKey('env-${state.environment}'),
                        initialValue: state.environment,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          isDense: true,
                          labelText: 'Environment',
                        ),
                        items: const [
                          DropdownMenuItem(value: 'dev', child: Text('dev')),
                          DropdownMenuItem(
                            value: 'preprod',
                            child: Text('preprod'),
                          ),
                          DropdownMenuItem(value: 'prod', child: Text('prod')),
                        ],
                        onChanged: (v) {
                          if (v != null) cubit.setEnvironment(v);
                        },
                      ),
                      const SizedBox(height: 8),
                      Chip(
                        visualDensity: VisualDensity.compact,
                        label: Text('${state.filteredServices.length} services'),
                      ),
                      const SizedBox(height: 8),
                      if (state.loading)
                        const Expanded(
                          child: Center(child: CircularProgressIndicator()),
                        )
                      else
                        Expanded(
                          child: ListView.builder(
                            itemCount: state.filteredServices.length,
                            itemBuilder: (context, i) {
                              final id = state.filteredServices[i];
                              final selected = id == state.selectedService;
                              return ListTile(
                                dense: true,
                                selected: selected,
                                title: Text(
                                  state.labelFor(id),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                subtitle: Text(
                                  id,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                                onTap: () {
                                  context.go('${AppRoutes.services}/$id');
                                  cubit.selectService(id);
                                },
                              );
                            },
                          ),
                        ),
                    ],
                  );
                },
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: BlocBuilder<ServicesCubit, ServicesState>(
              builder: (context, state) {
                if (state.error != null && state.overview == null) {
                  return GlassCard(
                    child: Center(child: Text(state.error!)),
                  );
                }
                if (state.overviewLoading && state.overview == null) {
                  return const GlassCard(
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                if (state.selectedService == null) {
                  return const GlassCard(
                    child: Center(child: Text('Select a service')),
                  );
                }
                return _OverviewBody(state: state);
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _OverviewBody extends StatelessWidget {
  const _OverviewBody({required this.state});

  final ServicesState state;

  @override
  Widget build(BuildContext context) {
    final ov = state.overview ?? const <String, dynamic>{};
    final service = asMap(ov['service']);
    final plugin = ov['plugin'] is Map
        ? Map<String, dynamic>.from(ov['plugin'] as Map)
        : null;
    final catalog = asMap(ov['catalog']);
    final openapi = asMap(ov['openapi']);
    final payloads = asMap(ov['payloads']);
    final coverage = asMap(ov['coverage']);
    final scenarios = asMap(ov['scenarios']);
    final metrics = asMap(ov['metrics']);
    final skills = mapList(ov['skills']);
    final features = mapList(ov['features']);
    final useCases = mapList(ov['use_cases']).isNotEmpty
        ? mapList(ov['use_cases'])
        : features;
    final warnings = (ov['warnings'] is List)
        ? (ov['warnings'] as List).map((e) => '$e').toList()
        : <String>[];
    final label = '${service['label'] ?? state.selectedService}';
    final inventComplete = scenarios['invent_complete'] == true;

    return ListView(
      children: [
        GlassCard(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      label,
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ),
                  IconButton(
                    tooltip: 'Refresh',
                    onPressed: () => context.read<ServicesCubit>().refresh(),
                    icon: state.overviewLoading
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
                '${state.selectedService} · ${state.environment}',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppColors.textSecondaryDark,
                    ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  if (plugin != null)
                    Chip(
                      visualDensity: VisualDensity.compact,
                      avatar: Icon(
                        plugin['enabled'] == true
                            ? Icons.check_circle
                            : Icons.pause_circle,
                        size: 16,
                      ),
                      label: Text(
                        'plugin ${plugin['enabled'] == true ? 'on' : 'off'}',
                      ),
                    ),
                  Chip(
                    visualDensity: VisualDensity.compact,
                    label: Text(
                      inventComplete ? 'invent complete' : 'invent incomplete',
                    ),
                  ),
                  if (catalog['target_url'] != null)
                    Chip(
                      visualDensity: VisualDensity.compact,
                      label: Text('${catalog['target_url']}'),
                    ),
                  _MetricChip(
                    'pass',
                    metrics['recent_pass_rate'] != null
                        ? '${metrics['recent_pass_rate']}%'
                        : '—',
                  ),
                  _MetricChip('p90', _fmtNum(metrics['last_p90_ms'], 'ms')),
                  _MetricChip('APIs', '${catalog['apis_count'] ?? 0}'),
                  _MetricChip('scenarios', '${scenarios['count'] ?? 0}'),
                  _MetricChip(
                    'quality',
                    coverage['quality_score'] != null
                        ? '${coverage['quality_score']}'
                        : '—',
                  ),
                ],
              ),
              if (warnings.isNotEmpty) ...[
                const SizedBox(height: 12),
                Material(
                  color: Colors.amber.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                  child: Padding(
                    padding: const EdgeInsets.all(10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Partial data',
                          style: Theme.of(context)
                              .textTheme
                              .labelLarge
                              ?.copyWith(fontWeight: FontWeight.w600),
                        ),
                        ...warnings.map((w) => Text('• $w')),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 12),
        CoverageBoard(
          skills: skills,
          useCases: useCases,
          serviceId: state.selectedService ?? '',
          environment: state.environment,
          onRun: () async {
            final svc = state.selectedService;
            if (svc == null || svc.isEmpty) return;
            final messenger = ScaffoldMessenger.of(context);
            messenger.showSnackBar(
              SnackBar(
                content: Text('Starting OpenAPI load for $svc (all APIs)…'),
                behavior: SnackBarBehavior.floating,
              ),
            );
            try {
              final exec = getIt<ExecuteRepository>();
              final out = await exec.execute(
                service: svc,
                audience: 'developer',
                environment: state.environment,
                testType: 'k6',
                profile: 'load',
                vus: 20,
                calls: 50,
                // null apiIds → every OpenAPI operation for this service
              );
              final runId = '${out['id'] ?? out['run_id'] ?? ''}';
              if (runId.isNotEmpty && context.mounted) {
                context.go('${AppRoutes.runs}/$runId');
              }
            } catch (e) {
              messenger.showSnackBar(
                SnackBar(
                  content: Text('Run failed: $e'),
                  behavior: SnackBarBehavior.floating,
                ),
              );
            }
          },
        ),
        const SizedBox(height: 12),
        GlassCard(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Catalog · OpenAPI · payloads',
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  Chip(
                    label: Text(
                      'APIs ${catalog['apis_count'] ?? 0}'
                      '${catalog['runtime'] != null ? ' · ${catalog['runtime']}' : ''}',
                    ),
                  ),
                  Chip(
                    avatar: Icon(
                      openapi['ok'] == true ? Icons.check : Icons.error_outline,
                      size: 16,
                    ),
                    label: Text(
                      openapi['ok'] == true
                          ? 'OpenAPI ${openapi['path_count'] ?? 0} paths'
                          : 'OpenAPI unavailable',
                    ),
                  ),
                  Chip(
                    label: Text(
                      payloads['active_version'] != null
                          ? 'payload set v${payloads['active_version']} · '
                              '${payloads['api_count'] ?? 0} apis'
                          : 'no active payload set',
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed: () {
                      final svc = state.selectedService;
                      if (svc == null) return;
                      context.go('${AppRoutes.specs}?spec=$svc');
                    },
                    icon: const Icon(Icons.api_outlined, size: 18),
                    label: const Text('Open OpenAPI'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () {
                      final svc = state.selectedService;
                      if (svc == null) return;
                      context.go('${AppRoutes.specs}?spec=$svc');
                    },
                    icon: const Icon(Icons.data_object, size: 18),
                    label: const Text('Manage payloads'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () {
                      final svc = state.selectedService;
                      if (svc == null) return;
                      context.go('${AppRoutes.runs}?service=$svc');
                    },
                    icon: const Icon(Icons.play_circle_outline, size: 18),
                    label: const Text('All runs'),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        GlassCard(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Text(
                    'Recent runs',
                    style: Theme.of(context)
                        .textTheme
                        .titleMedium
                        ?.copyWith(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(width: 8),
                  Chip(
                    visualDensity: VisualDensity.compact,
                    label: Text(
                      '${state.filteredRuns.length} shown'
                      '${ov['runs_total'] != null ? ' / ${ov['runs_total']} total' : ''}',
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  SizedBox(
                    width: 140,
                    child: DropdownButtonFormField<String>(
                      key: ValueKey('run-status-${state.runStatusFilter}'),
                      initialValue: state.runStatusFilter.isEmpty
                          ? ''
                          : state.runStatusFilter,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        isDense: true,
                        labelText: 'Status',
                      ),
                      items: const [
                        DropdownMenuItem(value: '', child: Text('all')),
                        DropdownMenuItem(
                          value: 'passed',
                          child: Text('passed'),
                        ),
                        DropdownMenuItem(
                          value: 'failed',
                          child: Text('failed'),
                        ),
                        DropdownMenuItem(
                          value: 'running',
                          child: Text('running'),
                        ),
                        DropdownMenuItem(
                          value: 'error',
                          child: Text('error'),
                        ),
                      ],
                      onChanged: (v) => context
                          .read<ServicesCubit>()
                          .setRunStatusFilter(v ?? ''),
                    ),
                  ),
                  SizedBox(
                    width: 220,
                    child: TextField(
                      decoration: const InputDecoration(
                        isDense: true,
                        labelText: 'Filter runs',
                        hintText: 'id / who / config',
                      ),
                      onChanged: context.read<ServicesCubit>().setRunQuery,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              if (state.filteredRuns.isEmpty)
                const Text('No runs for this service')
              else
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: DataTable(
                    showCheckboxColumn: false,
                    columns: const [
                      DataColumn(label: Text('ID')),
                      DataColumn(label: Text('Status')),
                      DataColumn(label: Text('Who')),
                      DataColumn(label: Text('Started')),
                      DataColumn(label: Text('Pass/Fail')),
                      DataColumn(label: Text('Fail%')),
                      DataColumn(label: Text('p90')),
                      DataColumn(label: Text('RPS')),
                      DataColumn(label: Text('Config')),
                    ],
                    rows: [
                      for (final r in state.filteredRuns)
                        DataRow(
                          onSelectChanged: (_) {
                            final id = '${r['id'] ?? ''}';
                            if (id.isNotEmpty) context.go('/runs/$id');
                          },
                          cells: [
                            DataCell(
                              Text(
                                _shortId('${r['id'] ?? ''}'),
                                style: const TextStyle(
                                  color: AppColors.primary,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                            DataCell(Text('${r['status'] ?? '—'}')),
                            DataCell(Text('${r['triggered_by'] ?? '—'}')),
                            DataCell(Text(_shortTs('${r['started_at'] ?? ''}'))),
                            DataCell(
                              Text(
                                '${r['api_pass_count'] ?? '—'} / ${r['api_fail_count'] ?? '—'}',
                              ),
                            ),
                            DataCell(Text(_fmtNum(r['fail_pct'], '%'))),
                            DataCell(Text(_fmtNum(r['p90_ms'], 'ms'))),
                            DataCell(Text(_fmtNum(r['rps'], ''))),
                            DataCell(Text('${r['config_name'] ?? '—'}')),
                          ],
                        ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _MetricChip extends StatelessWidget {
  const _MetricChip(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Chip(
      visualDensity: VisualDensity.compact,
      label: Text('$label $value'),
    );
  }
}

String _fmtNum(Object? v, String suffix) {
  if (v == null) return '—';
  if (v is num) {
    final s = v % 1 == 0 ? v.toInt().toString() : v.toStringAsFixed(1);
    return suffix.isEmpty ? s : '$s$suffix';
  }
  return '$v$suffix';
}

String _shortId(String id) {
  if (id.length <= 18) return id;
  return '${id.substring(0, 8)}…${id.substring(id.length - 6)}';
}

String _shortTs(String ts) {
  if (ts.isEmpty) return '—';
  final t = DateTime.tryParse(ts);
  if (t == null) return ts.length > 19 ? ts.substring(0, 19) : ts;
  final l = t.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${l.year}-${two(l.month)}-${two(l.day)} ${two(l.hour)}:${two(l.minute)}';
}
