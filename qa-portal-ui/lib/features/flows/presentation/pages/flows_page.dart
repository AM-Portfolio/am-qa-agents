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

class _FlowsView extends StatelessWidget {
  const _FlowsView();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<FlowsCubit, FlowsState>(
      builder: (context, state) {
        return Row(
          children: [
            SizedBox(
              width: 280,
              child: Material(
                color: Theme.of(context).colorScheme.surfaceContainerLow,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                      child: Text(
                        'API Flows',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                    if (state.loading)
                      const LinearProgressIndicator(minHeight: 2),
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
                        onSelect: (id) =>
                            context.read<FlowsCubit>().selectFlow(id),
                      ),
                    ),
                    const Divider(height: 1),
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
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
            ),
            const VerticalDivider(width: 1),
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
                  Expanded(
                    child: state.graph == null || state.graph!.isEmpty
                        ? const Center(child: Text('Select a flow'))
                        : FlowCanvas(
                            graph: state.graph!,
                            execution: state.execution,
                            executing: state.executing,
                            selectedLogNodeId: state.selectedLogNodeId,
                            nodeQuickResults: state.nodeQuickResults,
                            graphEpoch: Object.hash(
                              state.graph.hashCode,
                              state.graphDirty,
                              state.nodeQuickResults.hashCode,
                            ),
                            onRun: () =>
                                context.read<FlowsCubit>().runSelected(),
                            onSelectNode: (id) =>
                                context.read<FlowsCubit>().selectLogNode(id),
                            onQuickTest: (id) =>
                                context.read<FlowsCubit>().quickTestNode(id),
                            onAddAfter: (id) => addFlowToolAfter(context, id),
                            onDelete: (id) =>
                                context.read<FlowsCubit>().deleteNode(id),
                          ),
                  ),
                  if (state.selectedFlowId != null)
                    SizedBox(
                      height: MediaQuery.sizeOf(context).height * 0.38,
                      child: FlowsBottomBand(state: state),
                    ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}
