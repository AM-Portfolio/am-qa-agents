import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../observability/presentation/widgets/observability_attach.dart';
import '../cubit/flows_cubit.dart';
import '../cubit/flows_state.dart';
import 'flows_run_logs.dart';
import 'flows_variables_panel.dart';

class FlowsBottomBand extends StatelessWidget {
  const FlowsBottomBand({
    required this.state,
    this.onCollapse,
  });

  final FlowsState state;
  final VoidCallback? onCollapse;

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<FlowsCubit>();
    final ex = state.execution;
    final obs = ex?['observability_resources'] is Map
        ? Map<String, dynamic>.from(ex!['observability_resources'] as Map)
        : null;
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 6, 4, 0),
            child: Row(
              children: [
                Expanded(
                  child: SegmentedButton<int>(
                    segments: const [
                      ButtonSegment(value: 0, label: Text('Step traces')),
                      ButtonSegment(value: 1, label: Text('Variables')),
                    ],
                    selected: {state.bottomTab},
                    onSelectionChanged: (s) => cubit.setBottomTab(s.first),
                  ),
                ),
                if (onCollapse != null)
                  IconButton(
                    tooltip: 'Hide panel',
                    visualDensity: VisualDensity.compact,
                    onPressed: onCollapse,
                    icon: const Icon(Icons.unfold_less, size: 20),
                  ),
              ],
            ),
          ),
          if (state.bottomTab == 0 &&
              ex != null &&
              ('${ex['trace_id'] ?? ''}'.isNotEmpty || obs != null))
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
              child: ObservabilityAttach(
                compact: true,
                traceId: ex['trace_id']?.toString(),
                correlationId: ex['correlation_id']?.toString(),
                observabilityResources: obs,
                loadLogs: state.executionId == null
                    ? null
                    : () => cubit.loadExecutionObsLogs(),
              ),
            ),
          Expanded(
            child: state.bottomTab == 1
                ? FlowsVariablesPanel(state: state)
                : FlowsRunLogsPanel(
                    graph: state.graph,
                    execution: state.execution,
                    selectedNodeId: state.selectedLogNodeId,
                    nodeQuickResults: state.nodeQuickResults,
                    recentExecutions: state.recentExecutions,
                    filterStatus: state.execFilterStatus,
                    filterFlowId: state.execFilterFlowId,
                    filterEnv: state.execFilterEnv,
                    onSelect: (id) => cubit.selectLogNode(id),
                    onFilter: ({String? status, String? flowId, String? env}) {
                      cubit.setExecFilter(
                        status: status,
                        flowId: flowId,
                        env: env,
                      );
                    },
                    onOpenExecution: cubit.openExecution,
                  ),
          ),
        ],
      ),
    );
  }
}


