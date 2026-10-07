import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../domain/try_draft.dart';
import '../cubit/specs_cubit.dart';
import '../tabs/data_tab.dart';
import '../tabs/mcp_tab.dart';
import '../tabs/swagger_tab.dart';
import '../tabs/test_tab.dart';
import '../tabs/usecases_tab.dart';
import 'api_rail.dart';
import 'catalog_rail.dart';
import 'specs_shared_filters.dart';

class SpecsShell extends StatefulWidget {
  const SpecsShell({super.key});

  @override
  State<SpecsShell> createState() => _SpecsShellState();
}

class _SpecsShellState extends State<SpecsShell> with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  String _serviceQuery = '';
  String _apiQuery = '';

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 5, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  List<String> _filteredServices(SpecsState state) {
    final q = _serviceQuery.trim().toLowerCase();
    if (q.isEmpty) return state.services;
    return state.services.where((id) {
      final label = state.labelFor(id).toLowerCase();
      return id.toLowerCase().contains(q) || label.contains(q);
    }).toList();
  }

  List<(int, Map<String, dynamic>)> _filteredApis(SpecsState state) {
    final q = _apiQuery.trim().toLowerCase();
    final out = <(int, Map<String, dynamic>)>[];
    for (var i = 0; i < state.apis.length; i++) {
      final api = state.apis[i];
      final id = SpecsCubit.apiId(api, i).toLowerCase();
      final method = '${api['method'] ?? ''}'.toLowerCase();
      final path = '${api['path'] ?? api['url'] ?? ''}'.toLowerCase();
      if (q.isEmpty || id.contains(q) || method.contains(q) || path.contains(q)) {
        out.add((i, api));
      }
    }
    return out;
  }

  Future<void> _showDiffDialog(BuildContext context, List<DraftFieldChange> diff) async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(diff.isEmpty ? 'Refresh payload ? no changes' : 'Refresh payload ? compare'),
        content: SizedBox(
          width: 720,
          child: diff.isEmpty
              ? const Text('Draft is unchanged after Ensure/refresh.')
              : SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      for (final c in diff) ...[
                        Text(
                          c.field,
                          style: Theme.of(ctx).textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                        const SizedBox(height: 4),
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Theme.of(ctx)
                                      .colorScheme
                                      .errorContainer
                                      .withValues(alpha: 0.35),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: SelectableText(
                                  'Before\n${c.before}',
                                  style: Theme.of(ctx).textTheme.bodySmall?.copyWith(
                                        fontFamily: 'monospace',
                                      ),
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Theme.of(ctx)
                                      .colorScheme
                                      .primaryContainer
                                      .withValues(alpha: 0.35),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: SelectableText(
                                  'After\n${c.after}',
                                  style: Theme.of(ctx).textTheme.bodySmall?.copyWith(
                                        fontFamily: 'monospace',
                                      ),
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                      ],
                    ],
                  ),
                ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              context.read<SpecsCubit>().clearPayloadDiff();
              Navigator.pop(ctx);
            },
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocListener(
      listeners: [
        BlocListener<SpecsCubit, SpecsState>(
          listenWhen: (p, n) => p.message != n.message && n.message != null,
          listener: (context, state) {
            final msg = state.message;
            if (msg == null) return;
            // MCP run progress/summary lives in the Report panel — no toast spam.
            if (msg.startsWith('Running ') || msg.startsWith('MCP run:')) return;
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
          },
        ),
        BlocListener<SpecsCubit, SpecsState>(
          listenWhen: (p, n) =>
              p.message != n.message && n.message != null && n.message!.startsWith('Refresh:'),
          listener: (context, state) {
            _showDiffDialog(context, state.lastPayloadDiff);
          },
        ),
      ],
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Theme.of(context).colorScheme.surface,
              AppColors.primary.withValues(alpha: 0.06),
              Theme.of(context).colorScheme.surface,
            ],
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(8, 6, 8, 8),
          child: BlocBuilder<SpecsCubit, SpecsState>(
            builder: (context, state) {
              // Only block the whole page on the very first catalog fetch.
              if (state.loading &&
                  state.services.isEmpty &&
                  state.health == null &&
                  state.apis.isEmpty) {
                return const Center(child: CircularProgressIndicator());
              }
              final cubit = context.read<SpecsCubit>();
              final services = _filteredServices(state);
              final apis = _filteredApis(state);
              return Column(
                children: [
                  // Sticky banner only for hard errors — MCP run status is in Report.
                  if (state.error != null && state.error!.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Material(
                        color: Colors.redAccent.withValues(alpha: 0.18),
                        borderRadius: BorderRadius.circular(8),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 8,
                          ),
                          child: Row(
                            children: [
                              const Icon(
                                Icons.error_outline,
                                size: 18,
                                color: Colors.redAccent,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  state.error!,
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ),
                              TextButton(
                                onPressed: state.selectedService == null
                                    ? () => cubit.boot()
                                    : () => cubit.selectService(
                                          state.selectedService!,
                                        ),
                                child: const Text('Retry'),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  Row(
                    children: [
                      Text(
                        state.selectedService == null
                            ? 'OpenAPI'
                            : state.labelFor(state.selectedService!),
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                      const SizedBox(width: 8),
                      if (state.targetUrl != null)
                        Flexible(
                          child: Text(
                            '${state.environment} · ${state.targetUrl}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  fontFamily: 'monospace',
                                  color: AppColors.textSecondaryDark,
                                ),
                          ),
                        ),
                      if (state.selectedService != null) ...[
                        const SizedBox(width: 8),
                        Chip(
                          visualDensity: VisualDensity.compact,
                          label: Text(
                            'APIs ${state.apis.length}'
                            ' · ops ${state.operationCount ?? state.openapi?['operation_count'] ?? '?'}'
                            ' · tools ${state.toolsCount ?? state.mcpTools.length}',
                            style: Theme.of(context).textTheme.labelSmall,
                          ),
                          backgroundColor: state.syncCountsMatch
                              ? const Color(0xFF22C55E).withValues(alpha: 0.18)
                              : Colors.amber.withValues(alpha: 0.2),
                        ),
                      ],
                      const Spacer(),
                      if (state.loading)
                        const Padding(
                          padding: EdgeInsets.only(left: 8),
                          child: SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Expanded(
                    child: Row(
                      children: [
                        SizedBox(
                          width: 200,
                          child: SpecsCatalogRail(
                            state: state,
                            cubit: cubit,
                            services: services,
                            onFilterChanged: (v) => setState(() => _serviceQuery = v),
                          ),
                        ),
                        const SizedBox(width: 8),
                        SizedBox(
                          width: 270,
                          child: SpecsApiRail(
                            state: state,
                            cubit: cubit,
                            apis: apis,
                            onFilterChanged: (v) => setState(() => _apiQuery = v),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: GlassCard(
                            padding: EdgeInsets.zero,
                            child: Column(
                              children: [
                                SpecsSharedFilters(state: state, cubit: cubit),
                                const Divider(height: 1),
                                TabBar(
                                  controller: _tabs,
                                  tabs: const [
                                    Tab(text: 'Test'),
                                    Tab(text: 'Swagger'),
                                    Tab(text: 'MCP / AI'),
                                    Tab(text: 'Use cases'),
                                    Tab(text: 'Data'),
                                  ],
                                ),
                                Expanded(
                                  child: TabBarView(
                                    controller: _tabs,
                                    children: [
                                      const SpecsTestTab(),
                                      SpecsSwaggerTab(
                                        onUseInTest: () {
                                          _tabs.index = 0;
                                          setState(() {});
                                        },
                                      ),
                                      SpecsMcpTab(state: state),
                                      SpecsUseCasesTab(state: state),
                                      SpecsDataTab(state: state),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

}

