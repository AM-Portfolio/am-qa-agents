import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/flows_cubit.dart';
import '../cubit/flows_state.dart';
import 'flows_run_logs.dart';
import 'flows_variables_panel.dart';

class FlowsBottomBand extends StatelessWidget {
  const FlowsBottomBand({required this.state});

  final FlowsState state;

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<FlowsCubit>();
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 6, 12, 0),
            child: SegmentedButton<int>(
              segments: const [
                ButtonSegment(value: 0, label: Text('Run logs')),
                ButtonSegment(value: 1, label: Text('Variables')),
              ],
              selected: {state.bottomTab},
              onSelectionChanged: (s) => cubit.setBottomTab(s.first),
            ),
          ),
          Expanded(
            child: state.bottomTab == 1
                ? FlowsVariablesPanel(state: state)
                : FlowsRunLogsPanel(
                    graph: state.graph,
                    execution: state.execution,
                    selectedNodeId: state.selectedLogNodeId,
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


