import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../flow_graph/graph_layout.dart';
import '../../../flows/presentation/widgets/json_preview.dart';
import '../../../observability/presentation/widgets/observability_attach.dart';
import '../cubit/ui_flows_cubit.dart';
import '../cubit/ui_flows_state.dart';

/// API-Flows-style bottom band: run timeline + Inputs/Outputs peek.
class UiFlowsBottomBand extends StatelessWidget {
  const UiFlowsBottomBand({
    super.key,
    required this.state,
    required this.absUrl,
  });

  final UiFlowsState state;
  final String Function(String url) absUrl;

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<UiFlowsCubit>();
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 6, 12, 0),
            child: Row(
              children: [
                Expanded(
                  child: SegmentedButton<int>(
                    segments: const [
                      ButtonSegment(value: 0, label: Text('Step traces')),
                      ButtonSegment(value: 1, label: Text('Step edit')),
                    ],
                    selected: {state.bottomTab},
                    onSelectionChanged: (s) => cubit.setBottomTab(s.first),
                  ),
                ),
                if (state.runId != null) ...[
                  const SizedBox(width: 8),
                  TextButton.icon(
                    onPressed: () => context.go('/runs/${state.runId}'),
                    icon: const Icon(Icons.open_in_new, size: 16),
                    label: const Text('Full Run page'),
                  ),
                ],
              ],
            ),
          ),
          if (state.bottomTab == 0 &&
              (state.runTraceId != null ||
                  state.observabilityResources != null))
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
              child: ObservabilityAttach(
                compact: true,
                traceId: state.runTraceId,
                correlationId: state.runCorrelationId,
                observabilityResources: state.observabilityResources,
                loadLogs: state.runId == null
                    ? null
                    : () => context.read<UiFlowsCubit>().loadObsLogs(),
              ),
            ),
          Expanded(
            child: state.bottomTab == 1
                ? _StepEditHint(state: state)
                : _RunLogs(state: state, absUrl: absUrl),
          ),
        ],
      ),
    );
  }
}

class _StepEditHint extends StatelessWidget {
  const _StepEditHint({required this.state});
  final UiFlowsState state;

  @override
  Widget build(BuildContext context) {
    final id = state.selectedNodeId;
    if (id == null || id == kManualTriggerId) {
      return const Center(
        child: Text('Select a step card on the canvas to edit its label'),
      );
    }
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Text(
        'Selected: $id — use the label field above the canvas band, or click Apply after editing.',
        style: Theme.of(context).textTheme.bodyMedium,
      ),
    );
  }
}

class _RunLogs extends StatelessWidget {
  const _RunLogs({required this.state, required this.absUrl});
  final UiFlowsState state;
  final String Function(String url) absUrl;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final nodes = _timelineNodes(state);
    final selected = state.selectedNodeId;
    final ev = selected == null ? null : state.evidenceByNodeId[selected];
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 280,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      state.runId == null
                          ? 'No run yet — click Run or Start'
                          : '${state.runId} · ${state.runStatus ?? ''}'
                              '${state.runSummary != null ? ' · ${state.runSummary}' : ''}',
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                    if (state.runError != null && state.runError!.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(
                          state.runError!.split('\n').first,
                          maxLines: 4,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                color: Theme.of(context).colorScheme.error,
                                fontWeight: FontWeight.w600,
                              ),
                        ),
                      ),
                  ],
                ),
              ),
              Expanded(
                child: ListView.builder(
                  itemCount: nodes.length,
                  itemBuilder: (context, i) {
                    final n = nodes[i];
                    final id = '${n['id']}';
                    final e = state.evidenceByNodeId[id];
                    final status = '${e?['status'] ?? ''}';
                    final ms = durationMsFrom(e);
                    final selectedHere = selected == id;
                    Color? color;
                    if (status == 'ok') color = const Color(0xFF2E7D32);
                    if (status == 'fail') color = const Color(0xFFC62828);
                    if (status == 'running') color = const Color(0xFF1565C0);
                    return ListTile(
                      dense: true,
                      selected: selectedHere,
                      leading: Icon(
                        status == 'ok'
                            ? Icons.check_circle
                            : (status == 'fail'
                                ? Icons.cancel
                                : (status == 'running'
                                    ? Icons.timelapse
                                    : Icons.circle_outlined)),
                        color: color,
                        size: 18,
                      ),
                      title: Text(
                        '${n['label'] ?? id}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: Text(
                        [
                          if (status.isNotEmpty) status,
                          if (ms != null) '${ms.toStringAsFixed(1)}ms',
                        ].join(' · '),
                        style: Theme.of(context).textTheme.labelSmall,
                      ),
                      onTap: () =>
                          context.read<UiFlowsCubit>().selectNode(id),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        VerticalDivider(width: 1, color: scheme.outlineVariant),
        Expanded(
          child: ev == null
              ? Center(
                  child: Text(
                    state.runId == null
                        ? 'Run the flow to see Inputs / Outputs here'
                        : 'Select a step',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: scheme.onSurface.withValues(alpha: 0.55),
                        ),
                  ),
                )
              : DefaultTabController(
                  length: 3,
                  child: Column(
                    children: [
                      const TabBar(
                        tabs: [
                          Tab(text: 'Inputs'),
                          Tab(text: 'Outputs'),
                          Tab(text: 'Screenshot'),
                        ],
                      ),
                      Expanded(
                        child: TabBarView(
                          children: [
                            Padding(
                              padding: const EdgeInsets.all(8),
                              child: JsonPreview(
                                value: ev['request'],
                                emptyLabel: 'No input data',
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.all(8),
                              child: JsonPreview(
                                value: ev['error'] ?? ev['response'],
                                emptyLabel: 'No output data',
                              ),
                            ),
                            _ShotPane(
                              url: ev['screenshot_url']?.toString(),
                              absUrl: absUrl,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
        ),
      ],
    );
  }

  List<Map<String, dynamic>> _timelineNodes(UiFlowsState state) {
    final g = state.graph;
    if (g == null) return const [];
    final byId = <String, Map<String, dynamic>>{};
    for (final n in (g['nodes'] is List ? g['nodes'] as List : const [])) {
      if (n is Map) byId['${n['id']}'] = Map<String, dynamic>.from(n);
    }
    final outs = <String, List<String>>{};
    for (final e in (g['edges'] is List ? g['edges'] as List : const [])) {
      if (e is! Map) continue;
      outs.putIfAbsent('${e['from']}', () => []).add('${e['to']}');
    }
    final order = <String>[kManualTriggerId];
    var cur = kManualTriggerId;
    final seen = <String>{cur};
    while (true) {
      final nexts = outs[cur];
      if (nexts == null || nexts.isEmpty) break;
      final next = nexts.first;
      if (!seen.add(next)) break;
      order.add(next);
      cur = next;
    }
    // Fallback when edges are missing: show nodes left-to-right.
    if (order.length <= 1 && byId.length > 1) {
      final rest = byId.keys.where((id) => id != kManualTriggerId).toList()
        ..sort((a, b) {
          final ax = byId[a]?['x'] is num
              ? (byId[a]!['x'] as num).toDouble()
              : 0.0;
          final bx = byId[b]?['x'] is num
              ? (byId[b]!['x'] as num).toDouble()
              : 0.0;
          return ax.compareTo(bx);
        });
      order.addAll(rest);
    }
    return [
      for (final id in order)
        if (byId[id] != null) byId[id]!,
    ];
  }
}

class _ShotPane extends StatelessWidget {
  const _ShotPane({required this.url, required this.absUrl});
  final String? url;
  final String Function(String url) absUrl;

  @override
  Widget build(BuildContext context) {
    if (url == null || url!.trim().isEmpty) {
      return const Center(child: Text('No screenshot for this step'));
    }
    final resolved = absUrl(url!.trim());
    return Padding(
      padding: const EdgeInsets.all(8),
      child: InteractiveViewer(
        child: Image.network(
          resolved,
          fit: BoxFit.contain,
          errorBuilder: (_, __, ___) => const Center(
            child: Text('Could not load screenshot'),
          ),
        ),
      ),
    );
  }
}
