import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/config/portal_config.dart';
import '../../../../core/di/injection.dart';
import '../../../execute/data/execute_repository.dart';
import '../../../flow_graph/graph_layout.dart';
import '../../../flow_graph/ui_step_flow_canvas.dart';
import '../../../runs/data/runs_repository.dart';
import '../../data/ui_flows_repository.dart';
import '../cubit/ui_flows_cubit.dart';
import '../cubit/ui_flows_state.dart';
import '../widgets/ui_flows_bottom_band.dart';

class UiFlowsPage extends StatelessWidget {
  const UiFlowsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => UiFlowsCubit(
        getIt<UiFlowsRepository>(),
        getIt<ExecuteRepository>(),
        getIt<RunsRepository>(),
      )..load(),
      child: const _UiFlowsView(),
    );
  }
}

String _absUrl(String url) {
  final u = url.trim();
  if (u.isEmpty) return u;
  if (u.startsWith('http://') || u.startsWith('https://')) return u;
  final base = getIt<PortalConfig>().apiBase.replaceAll(RegExp(r'/+$'), '');
  return u.startsWith('/') ? '$base$u' : '$base/$u';
}

class _UiFlowsView extends StatelessWidget {
  const _UiFlowsView();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<UiFlowsCubit, UiFlowsState>(
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
                        'UI Flows',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                    if (state.loading)
                      const LinearProgressIndicator(minHeight: 2),
                    if (state.running)
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
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: Text(
                        state.agentOnline
                            ? 'Agent online'
                            : 'Agent offline${state.agentUrl != null ? ' · ${state.agentUrl}' : ''}',
                        style: Theme.of(context).textTheme.labelSmall,
                      ),
                    ),
                    Expanded(
                      child: _FlowsSidebar(
                        flows: state.flows,
                        selectedFlowId: state.selectedFlowId,
                        onSelect: (id) =>
                            context.read<UiFlowsCubit>().selectFlow(id),
                      ),
                    ),
                    const Divider(height: 1),
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          OutlinedButton.icon(
                            onPressed: () => _showCreateFlowDialog(context),
                            icon: const Icon(Icons.add, size: 18),
                            label: const Text('New flow'),
                          ),
                          const SizedBox(height: 8),
                          OutlinedButton.icon(
                            onPressed: () => _showSuitesDialog(context),
                            icon: const Icon(Icons.playlist_play, size: 18),
                            label: Text('Suites (${state.suites.length})'),
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
                  _Toolbar(state: state),
                  const Divider(height: 1),
                  if (state.selectedNodeId != null &&
                      state.selectedNodeId != kManualTriggerId &&
                      state.bottomTab == 1)
                    _NodeEditorBand(state: state),
                  Expanded(
                    child: state.graph == null
                        ? const Center(child: Text('Select a UI flow'))
                        : UiStepFlowCanvas(
                            graph: state.graph!,
                            evidenceByNodeId: state.evidenceByNodeId,
                            // Structural only — evidence/selection update in place.
                            // Including run status here disposed the controller every
                            // poll and wiped painted edges before node sizes measured.
                            graphEpoch: Object.hash(
                              state.graph.hashCode,
                              state.graphDirty,
                              (state.graph?['nodes'] is List)
                                  ? (state.graph!['nodes'] as List).length
                                  : 0,
                              (state.graph?['edges'] is List)
                                  ? (state.graph!['edges'] as List).length
                                  : 0,
                            ),
                            selectedNodeId: state.selectedNodeId,
                            resolveScreenshotUrl: _absUrl,
                            onSelectNode: (id) =>
                                context.read<UiFlowsCubit>().selectNode(id),
                            onRun: state.running
                                ? null
                                : () =>
                                    context.read<UiFlowsCubit>().runSelected(),
                            onAddAfter: state.running
                                ? null
                                : (id) => context
                                    .read<UiFlowsCubit>()
                                    .addStepAfter(id),
                            onDelete: state.running
                                ? null
                                : (id) =>
                                    context.read<UiFlowsCubit>().deleteNode(id),
                          ),
                  ),
                  if (state.selectedFlowId != null)
                    SizedBox(
                      height: MediaQuery.sizeOf(context).height * 0.36,
                      child: UiFlowsBottomBand(
                        state: state,
                        absUrl: _absUrl,
                      ),
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

class _Toolbar extends StatelessWidget {
  const _Toolbar({required this.state});
  final UiFlowsState state;

  @override
  Widget build(BuildContext context) {
    final flow = state.selectedFlow;
    final label = flow == null
        ? 'UI Flows'
        : '${flow['label'] ?? state.selectedFlowId}';
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: Theme.of(context).textTheme.titleSmall),
                if (flow != null)
                  Text(
                    [
                      '${flow['group'] ?? ''}',
                      'runs_as ${flow['runs_as'] ?? state.selectedFlowId}',
                      if (state.runStatus != null) state.runStatus!,
                      if (state.runSummary != null) state.runSummary!,
                    ].where((s) => s.trim().isNotEmpty).join(' · '),
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
              ],
            ),
          ),
          if (state.graphDirty)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Text(
                'Unsaved',
                style: TextStyle(
                  color: Theme.of(context).colorScheme.tertiary,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          FilledButton.tonalIcon(
            onPressed: state.saving || state.graph == null || state.running
                ? null
                : () => context.read<UiFlowsCubit>().saveGraph(),
            icon: state.saving
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.save_outlined, size: 18),
            label: const Text('Save graph'),
          ),
          const SizedBox(width: 8),
          FilledButton.icon(
            onPressed: state.running || state.selectedFlowId == null
                ? null
                : () => context.read<UiFlowsCubit>().runSelected(),
            icon: state.running
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.play_arrow, size: 18),
            label: Text(state.running ? 'Running…' : 'Run'),
          ),
        ],
      ),
    );
  }
}

class _NodeEditorBand extends StatefulWidget {
  const _NodeEditorBand({required this.state});
  final UiFlowsState state;

  @override
  State<_NodeEditorBand> createState() => _NodeEditorBandState();
}

class _NodeEditorBandState extends State<_NodeEditorBand> {
  late final TextEditingController _controller;
  String? _boundNodeId;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: _labelFor(widget.state));
    _boundNodeId = widget.state.selectedNodeId;
  }

  @override
  void didUpdateWidget(covariant _NodeEditorBand oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.state.selectedNodeId != _boundNodeId) {
      _boundNodeId = widget.state.selectedNodeId;
      _controller.text = _labelFor(widget.state);
    }
  }

  String _labelFor(UiFlowsState state) {
    final id = state.selectedNodeId;
    if (id == null) return '';
    for (final n in (state.graph?['nodes'] is List
        ? state.graph!['nodes'] as List
        : const [])) {
      if (n is Map && '${n['id']}' == id) {
        return '${n['label'] ?? ''}';
      }
    }
    return '';
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        child: Row(
          children: [
            Text('Step', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(width: 12),
            Expanded(
              child: TextField(
                controller: _controller,
                decoration: const InputDecoration(
                  isDense: true,
                  border: OutlineInputBorder(),
                  labelText: 'Label',
                ),
                onSubmitted: (v) =>
                    context.read<UiFlowsCubit>().renameSelectedNode(v),
              ),
            ),
            const SizedBox(width: 8),
            TextButton(
              onPressed: () => context
                  .read<UiFlowsCubit>()
                  .renameSelectedNode(_controller.text),
              child: const Text('Apply'),
            ),
          ],
        ),
      ),
    );
  }
}

class _FlowsSidebar extends StatelessWidget {
  const _FlowsSidebar({
    required this.flows,
    required this.selectedFlowId,
    required this.onSelect,
  });

  final List<Map<String, dynamic>> flows;
  final String? selectedFlowId;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    final groups = <String, List<Map<String, dynamic>>>{};
    for (final f in flows) {
      final g = '${f['group'] ?? 'Other'}';
      groups.putIfAbsent(g, () => []).add(f);
    }
    final keys = groups.keys.toList()..sort();
    return ListView(
      children: [
        for (final g in keys) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Text(
              g,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ),
          for (final f in groups[g]!)
            ListTile(
              dense: true,
              selected: '${f['id']}' == selectedFlowId,
              title: Text(
                '${f['label'] ?? f['id']}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              subtitle: Text(
                '${f['id']}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall,
              ),
              onTap: () => onSelect('${f['id']}'),
            ),
        ],
      ],
    );
  }
}

Future<void> _showCreateFlowDialog(BuildContext context) async {
  final cubit = context.read<UiFlowsCubit>();
  final idCtrl = TextEditingController();
  final labelCtrl = TextEditingController();
  final runsAsCtrl = TextEditingController();
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('New UI flow'),
      content: SizedBox(
        width: 360,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: idCtrl,
              decoration: const InputDecoration(
                labelText: 'ID (A-Z0-9_)',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: labelCtrl,
              decoration: const InputDecoration(
                labelText: 'Label',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: runsAsCtrl,
              decoration: const InputDecoration(
                labelText: 'runs_as (agent profile)',
                border: OutlineInputBorder(),
                helperText: 'Builtin profile id that Playwright executes',
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(ctx, true),
          child: const Text('Create'),
        ),
      ],
    ),
  );
  if (ok != true || !context.mounted) return;
  try {
    final id = idCtrl.text.trim().toUpperCase();
    await cubit.saveFlow({
      'id': id,
      'label': labelCtrl.text.trim().isEmpty ? id : labelCtrl.text.trim(),
      'group': 'Custom',
      'runs_as': runsAsCtrl.text.trim().isEmpty ? id : runsAsCtrl.text.trim(),
      'steps': ['Open target URL', 'Complete primary action', 'Verify outcome'],
      'verifications': ['No hard error'],
      'graph': graphFromStepLists(
        flowId: id,
        steps: ['Open target URL', 'Complete primary action', 'Verify outcome'],
        verifications: ['No hard error'],
      ),
    });
  } catch (e) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }
}

Future<void> _showSuitesDialog(BuildContext context) async {
  final cubit = context.read<UiFlowsCubit>();
  await showDialog<void>(
    context: context,
    builder: (ctx) {
      return BlocProvider.value(
        value: cubit,
        child: BlocBuilder<UiFlowsCubit, UiFlowsState>(
          builder: (context, state) {
            return AlertDialog(
              title: const Text('UI suites'),
              content: SizedBox(
                width: 420,
                height: 360,
                child: state.suites.isEmpty
                    ? const Center(child: Text('No suites'))
                    : ListView.separated(
                        itemCount: state.suites.length,
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (_, i) {
                          final s = state.suites[i];
                          final profiles = s['profiles'] is List
                              ? (s['profiles'] as List).join(', ')
                              : '';
                          return ListTile(
                            title: Text('${s['label'] ?? s['id']}'),
                            subtitle: Text(
                              '${s['id']}\n$profiles',
                              maxLines: 3,
                            ),
                            isThreeLine: true,
                            trailing: IconButton(
                              tooltip: 'Run suite (stays on this page)',
                              icon: const Icon(Icons.play_arrow),
                              onPressed: state.running
                                  ? null
                                  : () async {
                                      Navigator.pop(ctx);
                                      await context
                                          .read<UiFlowsCubit>()
                                          .runSuite('${s['id']}');
                                    },
                            ),
                          );
                        },
                      ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Close'),
                ),
              ],
            );
          },
        ),
      );
    },
  );
}
