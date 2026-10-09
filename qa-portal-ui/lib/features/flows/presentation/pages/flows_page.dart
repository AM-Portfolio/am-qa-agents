import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/di/injection.dart';
import '../../data/flows_repository.dart';
import '../cubit/flows_cubit.dart';
import '../cubit/flows_state.dart';

export '../cubit/flows_cubit.dart';
export '../cubit/flows_state.dart';
import '../widgets/credentials_manager.dart';
import '../widgets/flow_canvas.dart';
import '../widgets/flows_bottom_band.dart';
import '../widgets/flows_dialogs.dart';
import '../widgets/flows_node_inspector.dart';
import '../widgets/flows_sidebar.dart';
import '../widgets/flows_toolbar.dart';

class FlowsPage extends StatelessWidget {
  const FlowsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => FlowsCubit(getIt<FlowsRepository>())..load(),
      child: const _FlowsView(),
    );
  }
}

class _FlowsView extends StatefulWidget {
  const _FlowsView();

  @override
  State<_FlowsView> createState() => _FlowsViewState();
}

class _FlowsViewState extends State<_FlowsView> {
  static const _sidebarMin = 220.0;
  static const _sidebarMax = 520.0;
  static const _sidebarDefault = 320.0;
  static const _sidebarCollapsedW = 40.0;
  static const _bottomMin = 140.0;
  static const _bottomCollapsedH = 36.0;

  bool _sidebarOpen = true;
  double _sidebarWidth = _sidebarDefault;
  bool _bottomOpen = true;
  double _bottomHeight = 280;

  @override
  Widget build(BuildContext context) {
    final screenH = MediaQuery.sizeOf(context).height;
    final bottomMax = (screenH * 0.55).clamp(220.0, 560.0);

    return BlocBuilder<FlowsCubit, FlowsState>(
      builder: (context, state) {
        return Row(
          children: [
            _buildSidebar(context, state),
            _sidebarResizeHandle(),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  FlowsToolbar(
                    state: state,
                    onSchedule: () => showFlowsScheduleDialog(context),
                    onSuite: () => showFlowsSuiteDialog(context),
                    onSaveGraph: () => saveFlowsGraph(context),
                  ),
                  const Divider(height: 1),
                  if (state.selectedLogNodeId != null &&
                      state.selectedLogNodeId != '__manual_trigger__')
                    FlowsNodeInspector(state: state),
                  Expanded(
                    child: state.graph == null || state.graph!.isEmpty
                        ? const Center(child: Text('Select a flow'))
                        : Builder(
                            builder: (ctx) {
                              final cubit = ctx.read<FlowsCubit>();
                              var defaultSvc =
                                  '${state.graph?['api_pack'] ?? ''}'.trim();
                              if (defaultSvc.isEmpty &&
                                  state.catalogServices.isNotEmpty) {
                                defaultSvc = state.catalogServices.first;
                              }
                              return FlowCanvas(
                                graph: state.graph!,
                                execution: state.execution,
                                executing: state.executing,
                                selectedLogNodeId: state.selectedLogNodeId,
                                nodeQuickResults: state.nodeQuickResults,
                                graphEpoch: Object.hash(
                                  state.graph.hashCode,
                                  state.graphDirty,
                                  state.nodeQuickResults.hashCode,
                                  state.isDraft,
                                ),
                                onRun: () => cubit.runSelected(),
                                onSelectNode: cubit.selectLogNode,
                                onQuickTest: cubit.quickTestNode,
                                onCommitAdd: (id, stub) =>
                                    commitFlowToolAfter(ctx, id, stub),
                                onDelete: cubit.deleteNode,
                                listTools: cubit.listOpenApiTools,
                                listServices: cubit.listCatalogServices,
                                loadPayloadSet: (service, {int? version}) =>
                                    cubit.loadPayloadSet(
                                  service,
                                  version: version,
                                ),
                                defaultService: defaultSvc,
                                autoOpenCompose: state.isDraft,
                                allowRun: !state.isDraft,
                              );
                            },
                          ),
                  ),
                  if (state.selectedFlowId != null)
                    _buildBottomPanel(context, state, bottomMax),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildSidebar(BuildContext context, FlowsState state) {
    final cs = Theme.of(context).colorScheme;
    if (!_sidebarOpen) {
      return Material(
        color: cs.surfaceContainerLow,
        child: SizedBox(
          width: _sidebarCollapsedW,
          child: Column(
            children: [
              const SizedBox(height: 8),
              IconButton(
                tooltip: 'Expand flows sidebar',
                onPressed: () => setState(() => _sidebarOpen = true),
                icon: const Icon(Icons.chevron_right),
              ),
              RotatedBox(
                quarterTurns: 3,
                child: Text(
                  'Flows',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.6,
                      ),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return SizedBox(
      width: _sidebarWidth,
      child: Material(
        color: cs.surfaceContainerLow,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 10, 4, 4),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Flows',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  IconButton(
                    tooltip: 'Collapse sidebar',
                    visualDensity: VisualDensity.compact,
                    onPressed: () => setState(() => _sidebarOpen = false),
                    icon: const Icon(Icons.chevron_left, size: 20),
                  ),
                ],
              ),
            ),
            if (state.loading) const LinearProgressIndicator(minHeight: 2),
            if (state.error != null)
              Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  state.error!,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                    fontSize: 12,
                  ),
                ),
              ),
            Expanded(
              child: FlowsSidebar(
                flows: state.flows,
                selectedFlowId: state.selectedFlowId,
                flowQuery: state.flowQuery,
                categoryFilter: state.categoryFilter,
                apiPackFilter: state.apiPackFilter,
                facets: state.facets,
                catalogServices: state.catalogServices,
                flowsTotal: state.flowsTotal,
                loadingMore: state.loadingMore,
                hasMore: state.hasMoreFlows,
                onQueryChanged: (q) =>
                    context.read<FlowsCubit>().setFlowQuery(q),
                onCategoryFilter: (c) =>
                    context.read<FlowsCubit>().setCategoryFilter(c),
                onApiPackFilter: (p) =>
                    context.read<FlowsCubit>().setApiPackFilter(p),
                onLoadMore: () =>
                    context.read<FlowsCubit>().loadMoreFlows(),
                onLoadAll: () => context.read<FlowsCubit>().loadAllFlows(),
                onSelect: (id) => context.read<FlowsCubit>().selectFlow(id),
              ),
            ),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  OutlinedButton.icon(
                    onPressed: () => startNewFlowDraft(context),
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('New flow'),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: () => showFlowsProposeDialog(context),
                    icon: const Icon(Icons.auto_awesome, size: 18),
                    label: const Text('Propose scenarios'),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: () => showCredentialsManager(context),
                    icon: const Icon(Icons.key_outlined, size: 18),
                    label: const Text('Credentials'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sidebarResizeHandle() {
    if (!_sidebarOpen) {
      return const VerticalDivider(width: 1);
    }
    return MouseRegion(
      cursor: SystemMouseCursors.resizeColumn,
      child: GestureDetector(
        behavior: HitTestBehavior.translucent,
        onHorizontalDragUpdate: (d) {
          setState(() {
            _sidebarWidth =
                (_sidebarWidth + d.delta.dx).clamp(_sidebarMin, _sidebarMax);
          });
        },
        onDoubleTap: () => setState(() => _sidebarWidth = _sidebarDefault),
        child: SizedBox(
          width: 6,
          child: Center(
            child: Container(
              width: 2,
              height: 36,
              decoration: BoxDecoration(
                color: Theme.of(context)
                    .colorScheme
                    .outlineVariant
                    .withValues(alpha: 0.9),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildBottomPanel(
    BuildContext context,
    FlowsState state,
    double bottomMax,
  ) {
    final cs = Theme.of(context).colorScheme;

    if (!_bottomOpen) {
      return Material(
        color: cs.surfaceContainerLow,
        child: InkWell(
          onTap: () => setState(() => _bottomOpen = true),
          child: SizedBox(
            height: _bottomCollapsedH,
            child: Row(
              children: [
                const SizedBox(width: 12),
                Icon(Icons.unfold_more, size: 18, color: cs.primary),
                const SizedBox(width: 8),
                Text(
                  'Step traces',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
                const Spacer(),
                Text(
                  'Click to open',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: cs.onSurfaceVariant,
                      ),
                ),
                const SizedBox(width: 12),
              ],
            ),
          ),
        ),
      );
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        MouseRegion(
          cursor: SystemMouseCursors.resizeRow,
          child: GestureDetector(
            behavior: HitTestBehavior.translucent,
            onVerticalDragUpdate: (d) {
              setState(() {
                _bottomHeight =
                    (_bottomHeight - d.delta.dy).clamp(_bottomMin, bottomMax);
              });
            },
            onDoubleTap: () => setState(() {
              _bottomHeight = (MediaQuery.sizeOf(context).height * 0.38)
                  .clamp(_bottomMin, bottomMax);
            }),
            child: Container(
              height: 10,
              color: cs.surfaceContainerLow,
              alignment: Alignment.center,
              child: Container(
                width: 44,
                height: 3,
                decoration: BoxDecoration(
                  color: cs.outlineVariant,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
          ),
        ),
        SizedBox(
          height: _bottomHeight,
          child: FlowsBottomBand(
            state: state,
            onCollapse: () => setState(() => _bottomOpen = false),
          ),
        ),
      ],
    );
  }
}
