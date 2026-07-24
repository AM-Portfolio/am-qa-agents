import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../data/runs_repository.dart';
import '../cubit/runs_cubit.dart';

class RunsPage extends StatelessWidget {
  const RunsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => RunsCubit(getIt<RunsRepository>())..load(),
      child: const _RunsView(),
    );
  }
}

class _RunsView extends StatefulWidget {
  const _RunsView();

  @override
  State<_RunsView> createState() => _RunsViewState();
}

class _RunsViewState extends State<_RunsView> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final runId = GoRouterState.of(context).uri.queryParameters['run_id'];
      if (runId != null && runId.isNotEmpty) {
        context.go('/runs/$runId');
      }
    });
  }

  Future<void> _pickDate({
    required bool isFrom,
    required RunsCubit cubit,
    required String current,
  }) async {
    final now = DateTime.now();
    final initial = DateTime.tryParse(current) ?? now;
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(now.year - 3),
      lastDate: DateTime(now.year + 1),
    );
    if (picked == null) return;
    final formatted =
        '${picked.year.toString().padLeft(4, '0')}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
    if (isFrom) {
      cubit.setFrom(formatted);
    } else {
      cubit.setTo(formatted);
    }
    cubit.load();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          GlassCard(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: BlocBuilder<RunsCubit, RunsState>(
              builder: (context, state) {
                final cubit = context.read<RunsCubit>();
                return Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      'Runs',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                    Chip(
                      visualDensity: VisualDensity.compact,
                      label: Text('${state.total} total'),
                    ),
                    SizedBox(
                      width: 130,
                      child: DropdownButtonFormField<String>(
                        key: ValueKey('status-${state.status}'),
                        initialValue: state.status,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Status',
                          isDense: true,
                          border: OutlineInputBorder(),
                        ),
                        items: const [
                          DropdownMenuItem(value: '', child: Text('Any')),
                          DropdownMenuItem(value: 'running', child: Text('running')),
                          DropdownMenuItem(value: 'passed', child: Text('passed')),
                          DropdownMenuItem(value: 'failed', child: Text('failed')),
                          DropdownMenuItem(
                            value: 'cancelled',
                            child: Text('cancelled'),
                          ),
                        ],
                        onChanged: (v) {
                          cubit.setStatus(v ?? '');
                          cubit.load();
                        },
                      ),
                    ),
                    SizedBox(
                      width: 150,
                      child: TextFormField(
                        key: ValueKey('svc-${state.service}'),
                        initialValue: state.service,
                        decoration: const InputDecoration(
                          labelText: 'Service',
                          isDense: true,
                          border: OutlineInputBorder(),
                        ),
                        onChanged: cubit.setService,
                        onFieldSubmitted: (_) => cubit.load(),
                      ),
                    ),
                    SizedBox(
                      width: 120,
                      child: DropdownButtonFormField<String>(
                        key: ValueKey('env-${state.environment}'),
                        initialValue: state.environment,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Env',
                          isDense: true,
                          border: OutlineInputBorder(),
                        ),
                        items: const [
                          DropdownMenuItem(value: '', child: Text('Any')),
                          DropdownMenuItem(value: 'dev', child: Text('dev')),
                          DropdownMenuItem(value: 'preprod', child: Text('preprod')),
                          DropdownMenuItem(value: 'prod', child: Text('prod')),
                        ],
                        onChanged: (v) {
                          cubit.setEnvironment(v ?? '');
                          cubit.load();
                        },
                      ),
                    ),
                    SizedBox(
                      width: 140,
                      child: DropdownButtonFormField<String>(
                        key: ValueKey('tt-${state.testType}'),
                        initialValue: state.testType,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Type',
                          isDense: true,
                          border: OutlineInputBorder(),
                        ),
                        items: const [
                          DropdownMenuItem(value: '', child: Text('Any')),
                          DropdownMenuItem(value: 'k6', child: Text('k6')),
                          DropdownMenuItem(
                            value: 'playwright',
                            child: Text('playwright'),
                          ),
                          DropdownMenuItem(value: 'mixed', child: Text('mixed')),
                        ],
                        onChanged: (v) {
                          cubit.setTestType(v ?? '');
                          cubit.load();
                        },
                      ),
                    ),
                    SizedBox(
                      width: 150,
                      child: TextFormField(
                        key: ValueKey('from-${state.from}'),
                        initialValue: state.from,
                        decoration: InputDecoration(
                          labelText: 'From',
                          isDense: true,
                          border: const OutlineInputBorder(),
                          suffixIcon: IconButton(
                            icon: const Icon(Icons.calendar_today, size: 16),
                            onPressed: () => _pickDate(
                              isFrom: true,
                              cubit: cubit,
                              current: state.from,
                            ),
                          ),
                        ),
                        onChanged: cubit.setFrom,
                        onFieldSubmitted: (_) => cubit.load(),
                      ),
                    ),
                    SizedBox(
                      width: 150,
                      child: TextFormField(
                        key: ValueKey('to-${state.to}'),
                        initialValue: state.to,
                        decoration: InputDecoration(
                          labelText: 'To',
                          isDense: true,
                          border: const OutlineInputBorder(),
                          suffixIcon: IconButton(
                            icon: const Icon(Icons.calendar_today, size: 16),
                            onPressed: () => _pickDate(
                              isFrom: false,
                              cubit: cubit,
                              current: state.to,
                            ),
                          ),
                        ),
                        onChanged: cubit.setTo,
                        onFieldSubmitted: (_) => cubit.load(),
                      ),
                    ),
                    SizedBox(
                      width: 200,
                      child: TextFormField(
                        key: ValueKey('q-${state.q}'),
                        initialValue: state.q,
                        decoration: const InputDecoration(
                          labelText: 'Search / run id',
                          isDense: true,
                          border: OutlineInputBorder(),
                          prefixIcon: Icon(Icons.search, size: 18),
                        ),
                        onChanged: cubit.setQ,
                        onFieldSubmitted: (_) => cubit.load(),
                      ),
                    ),
                    OutlinedButton(
                      onPressed: () => cubit.load(),
                      child: const Text('Apply'),
                    ),
                    FilledButton.icon(
                      onPressed: () => cubit.load(),
                      icon: const Icon(Icons.refresh, size: 18),
                      label: const Text('Refresh'),
                    ),
                  ],
                );
              },
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: GlassCard(
              padding: EdgeInsets.zero,
              child: BlocBuilder<RunsCubit, RunsState>(
                builder: (context, state) {
                  if (state.loading && state.items.isEmpty) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (state.error != null && state.items.isEmpty) {
                    return Center(
                      child: Text(
                        state.error!,
                        style: TextStyle(color: Theme.of(context).colorScheme.error),
                      ),
                    );
                  }
                  if (state.items.isEmpty) {
                    return Center(
                      child: Text(
                        'No runs yet. Use Execute above to start a test.',
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                    );
                  }
                  return Column(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          border: Border(
                            bottom: BorderSide(
                              color: Theme.of(context).dividerColor.withValues(alpha: 0.5),
                            ),
                          ),
                        ),
                        child: Row(
                          children: [
                            const SizedBox(width: 28),
                            _colHeader(context, 'Status', flex: 2),
                            _colHeader(context, 'Name / id', flex: 4),
                            _colHeader(context, 'Type', flex: 2),
                            _colHeader(context, 'Svc / env', flex: 3),
                            _colHeader(context, 'VUs', flex: 1),
                            _colHeader(context, 'APIs · Pass/Fail', flex: 3),
                            _colHeader(context, 'Started', flex: 2),
                          ],
                        ),
                      ),
                      Expanded(
                        child: ListView.separated(
                          itemCount: state.items.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, i) {
                            final r = state.items[i];
                            final id = '${r['id'] ?? ''}';
                            final status = '${r['status'] ?? ''}';
                            final name = '${r['config_name'] ?? r['name'] ?? id}';
                            final testType = '${r['test_type'] ?? ''}';
                            final svc = '${r['service'] ?? ''}';
                            final env = '${r['environment'] ?? ''}';
                            final started = _fmtStarted(
                              '${r['started_at'] ?? r['created_at'] ?? ''}',
                            );
                            final vus = r['vus'] ??
                                (r['params'] is Map
                                    ? (r['params'] as Map)['vus']
                                    : null);
                            final apiCount = r['api_count'];
                            final passN = r['api_pass_count'] ??
                                r['passed_count'] ??
                                r['ok_count'];
                            final failN = r['api_fail_count'] ??
                                r['failed_count'] ??
                                r['fail_count'];
                            final passed = r['passed'];
                            final outcome = passed == true
                                ? 'PASS'
                                : (passed == false
                                    ? 'FAIL'
                                    : status.toUpperCase());
                            final shortId = id.length > 8 ? id.substring(0, 8) : id;
                            return InkWell(
                              onTap: id.isEmpty ? null : () => context.go('/runs/$id'),
                              child: Padding(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                  vertical: 10,
                                ),
                                child: Row(
                                  children: [
                                    _StatusDot(status: status),
                                    const SizedBox(width: 16),
                                    Expanded(
                                      flex: 2,
                                      child: Text(
                                        outcome,
                                        style: TextStyle(
                                          fontWeight: FontWeight.w600,
                                          color: passed == true
                                              ? Colors.green
                                              : (passed == false
                                                  ? Theme.of(context)
                                                      .colorScheme
                                                      .error
                                                  : null),
                                        ),
                                      ),
                                    ),
                                    Expanded(
                                      flex: 4,
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            name,
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            style: const TextStyle(
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                          Row(
                                            children: [
                                              Flexible(
                                                child: Text(
                                                  shortId,
                                                  maxLines: 1,
                                                  overflow: TextOverflow.ellipsis,
                                                  style: Theme.of(context)
                                                      .textTheme
                                                      .bodySmall
                                                      ?.copyWith(
                                                        fontFamily: 'monospace',
                                                      ),
                                                ),
                                              ),
                                              if (id.isNotEmpty)
                                                IconButton(
                                                  visualDensity:
                                                      VisualDensity.compact,
                                                  padding: EdgeInsets.zero,
                                                  constraints:
                                                      const BoxConstraints(
                                                    minWidth: 28,
                                                    minHeight: 28,
                                                  ),
                                                  tooltip: 'Copy run id',
                                                  icon: const Icon(
                                                    Icons.copy,
                                                    size: 14,
                                                  ),
                                                  onPressed: () async {
                                                    await Clipboard.setData(
                                                      ClipboardData(text: id),
                                                    );
                                                    if (!context.mounted) {
                                                      return;
                                                    }
                                                    ScaffoldMessenger.of(context)
                                                        .showSnackBar(
                                                      SnackBar(
                                                        content: Text(
                                                          'Copied $shortId…',
                                                        ),
                                                        duration:
                                                            const Duration(
                                                          seconds: 1,
                                                        ),
                                                      ),
                                                    );
                                                  },
                                                ),
                                            ],
                                          ),
                                        ],
                                      ),
                                    ),
                                    Expanded(flex: 2, child: Text(testType)),
                                    Expanded(
                                      flex: 3,
                                      child: Text(
                                        '$svc/$env',
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                    Expanded(
                                      flex: 1,
                                      child: Text(vus == null ? '—' : '$vus'),
                                    ),
                                    Expanded(
                                      flex: 3,
                                      child: _ApiCountsCell(
                                        apiCount: apiCount,
                                        passN: passN,
                                        failN: failN,
                                      ),
                                    ),
                                    Expanded(
                                      flex: 2,
                                      child: Text(
                                        started,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodySmall,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
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
          const SizedBox(height: 8),
          BlocBuilder<RunsCubit, RunsState>(
            builder: (context, state) {
              final cubit = context.read<RunsCubit>();
              final start = state.total == 0 ? 0 : state.offset + 1;
              final end = state.offset + state.items.length;
              return GlassCard(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                child: Row(
                  children: [
                    Text(
                      state.total == 0
                          ? 'No results'
                          : '$start–$end of ${state.total}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const Spacer(),
                    OutlinedButton(
                      onPressed:
                          state.hasPrev && !state.loading ? cubit.prevPage : null,
                      child: const Text('Prev'),
                    ),
                    const SizedBox(width: 8),
                    OutlinedButton(
                      onPressed:
                          state.hasNext && !state.loading ? cubit.nextPage : null,
                      child: const Text('Next'),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _colHeader(BuildContext context, String label, {required int flex}) {
    return Expanded(
      flex: flex,
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}

String _fmtStarted(String raw) {
  if (raw.isEmpty) return '—';
  final dt = DateTime.tryParse(raw);
  if (dt == null) return raw;
  final local = dt.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${local.year}-${two(local.month)}-${two(local.day)} '
      '${two(local.hour)}:${two(local.minute)}';
}

class _ApiCountsCell extends StatelessWidget {
  const _ApiCountsCell({
    required this.apiCount,
    required this.passN,
    required this.failN,
  });

  final Object? apiCount;
  final Object? passN;
  final Object? failN;

  @override
  Widget build(BuildContext context) {
    final hasAny = apiCount != null || passN != null || failN != null;
    if (!hasAny) {
      return Text('—', style: Theme.of(context).textTheme.bodySmall);
    }
    final total = apiCount ??
        ((passN is num ? passN as num : 0) + (failN is num ? failN as num : 0));
    final pass = passN ?? '—';
    final fail = failN ?? '—';
    final failNum = failN is num ? failN as num : null;
    return Text.rich(
      TextSpan(
        style: Theme.of(context).textTheme.bodySmall,
        children: [
          TextSpan(
            text: '$total',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const TextSpan(text: ' · '),
          TextSpan(
            text: '$pass✓',
            style: const TextStyle(color: Colors.green, fontWeight: FontWeight.w600),
          ),
          const TextSpan(text: ' '),
          TextSpan(
            text: '$fail✗',
            style: TextStyle(
              color: (failNum != null && failNum > 0)
                  ? Theme.of(context).colorScheme.error
                  : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.55),
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    );
  }
}

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      'passed' || 'completed' => Colors.green,
      'failed' || 'error' => Theme.of(context).colorScheme.error,
      'running' || 'pending' => AppColors.primary,
      'cancelled' => Colors.orange,
      _ => Theme.of(context).colorScheme.outline,
    };
    return CircleAvatar(radius: 6, backgroundColor: color);
  }
}
