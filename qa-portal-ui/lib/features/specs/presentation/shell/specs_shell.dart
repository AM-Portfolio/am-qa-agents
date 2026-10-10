import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../../domain/try_draft.dart';
import '../cubit/specs_cubit.dart';
import '../datasets/specs_datasets_view.dart';
import '../tabs/mcp_tab.dart';
import '../tabs/sdk_tab.dart';
import '../tabs/swagger_tab.dart';
import '../tabs/test_tab.dart';
import '../tabs/usecases_tab.dart';
import 'specs_collections_sidebar.dart';
import 'specs_primary_rail.dart';
import 'specs_resource_sidebar.dart';
import 'specs_shared_filters.dart';

class SpecsShell extends StatefulWidget {
  const SpecsShell({super.key});

  @override
  State<SpecsShell> createState() => _SpecsShellState();
}

class _SpecsShellState extends State<SpecsShell> {
  bool _primaryCollapsed = false;
  double _secondaryWidth = 300;
  static const _secondaryMin = 220.0;
  static const _secondaryMax = 420.0;
  static const _secondaryDefault = 300.0;

  Future<void> _showDiffDialog(
    BuildContext context,
    List<DraftFieldChange> diff,
  ) async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          diff.isEmpty ? 'Refresh payload — no changes' : 'Refresh payload — compare',
        ),
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
                                  style: Theme.of(ctx)
                                      .textTheme
                                      .bodySmall
                                      ?.copyWith(fontFamily: 'monospace'),
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
                                  style: Theme.of(ctx)
                                      .textTheme
                                      .bodySmall
                                      ?.copyWith(fontFamily: 'monospace'),
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

  Widget _secondaryPane(SpecsState state, SpecsCubit cubit) {
    if (state.navMode == SpecsNavMode.datasets) {
      // Datasets: filterable collection list + version hints live in body.
      return SpecsCollectionsSidebar(state: state, cubit: cubit);
    }
    // Collections: if no service yet → collection picker; else APIs+MCP.
    if (state.selectedService == null) {
      return SpecsCollectionsSidebar(state: state, cubit: cubit);
    }
    return Column(
      children: [
        SpecsCollectionsSidebar(
          state: state,
          cubit: cubit,
          showAsSwitcher: true,
        ),
        const Divider(height: 1),
        Expanded(
          child: SpecsResourceSidebar(
            state: state,
            cubit: cubit,
            onSelectApi: () {
              cubit.setWorkspaceTab(SpecsWorkspaceTab.test);
            },
            onSelectMcp: () {
              cubit.setWorkspaceTab(SpecsWorkspaceTab.mcp);
            },
          ),
        ),
      ],
    );
  }

  Widget _body(SpecsState state) {
    if (state.navMode == SpecsNavMode.datasets) {
      return GlassCard(
        padding: EdgeInsets.zero,
        child: SpecsDatasetsView(state: state),
      );
    }
    return GlassCard(
      padding: EdgeInsets.zero,
      child: Column(
        children: [
          SpecsSharedFilters(
            state: state,
            cubit: context.read<SpecsCubit>(),
            onOpenDatasets: () => context.go(AppRoutes.datasets),
          ),
          const Divider(height: 1),
          Expanded(
            // Build only the active surface so Swagger iframe / MCP stay cold.
            child: switch (state.workspaceTab) {
              SpecsWorkspaceTab.test => const SpecsTestTab(),
              SpecsWorkspaceTab.swagger => SpecsSwaggerTab(
                  onUseInTest: () {
                    context.read<SpecsCubit>().setWorkspaceTab(
                          SpecsWorkspaceTab.test,
                        );
                  },
                ),
              SpecsWorkspaceTab.mcp => SpecsMcpTab(state: state),
              SpecsWorkspaceTab.sdk => SpecsSdkTab(state: state),
              SpecsWorkspaceTab.usecases => SpecsUseCasesTab(state: state),
            },
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
            if (msg.startsWith('Running ') || msg.startsWith('MCP run:')) {
              return;
            }
            ScaffoldMessenger.of(context)
                .showSnackBar(SnackBar(content: Text(msg)));
          },
        ),
        BlocListener<SpecsCubit, SpecsState>(
          listenWhen: (p, n) =>
              p.message != n.message &&
              n.message != null &&
              n.message!.startsWith('Refresh:'),
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
              if (state.loading &&
                  state.services.isEmpty &&
                  state.health == null &&
                  state.apis.isEmpty) {
                return const Center(child: CircularProgressIndicator());
              }
              final cubit = context.read<SpecsCubit>();
              return Column(
                children: [
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
                        state.navMode == SpecsNavMode.datasets
                            ? 'Datasets'
                            : (state.selectedService == null
                                ? 'API'
                                : state.labelFor(state.selectedService!)),
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
                            style: Theme.of(context)
                                .textTheme
                                .bodySmall
                                ?.copyWith(
                                  fontFamily: 'monospace',
                                  color: AppColors.textSecondaryDark,
                                ),
                          ),
                        ),
                      if (state.selectedService != null &&
                          state.navMode == SpecsNavMode.collections) ...[
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
                      if (state.apisLoading ||
                          state.openapiLoading ||
                          state.mcpLoading ||
                          state.payloadListLoading)
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
                        if (state.navMode != SpecsNavMode.datasets) ...[
                          SpecsPrimaryRail(
                            state: state,
                            cubit: cubit,
                            collapsed: _primaryCollapsed,
                            onToggleCollapse: () => setState(
                              () => _primaryCollapsed = !_primaryCollapsed,
                            ),
                          ),
                          const SizedBox(width: 6),
                        ],
                        SizedBox(
                          width: _secondaryWidth,
                          child: _secondaryPane(state, cubit),
                        ),
                        MouseRegion(
                          cursor: SystemMouseCursors.resizeColumn,
                          child: GestureDetector(
                            behavior: HitTestBehavior.translucent,
                            onHorizontalDragUpdate: (d) {
                              setState(() {
                                _secondaryWidth = (_secondaryWidth + d.delta.dx)
                                    .clamp(_secondaryMin, _secondaryMax);
                              });
                            },
                            onDoubleTap: () => setState(
                              () => _secondaryWidth = _secondaryDefault,
                            ),
                            child: const SizedBox(
                              width: 6,
                              child: Center(
                                child: VerticalDivider(width: 1),
                              ),
                            ),
                          ),
                        ),
                        Expanded(child: _body(state)),
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
