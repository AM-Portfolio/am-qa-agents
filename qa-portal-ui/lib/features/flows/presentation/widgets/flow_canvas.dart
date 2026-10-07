import 'package:flutter/material.dart';
import 'package:node_flow/node_flow.dart';

import 'flow_node_card.dart';

class FlowCanvas extends StatefulWidget {
  const FlowCanvas({
    required this.graph,
    this.execution,
    this.executing = false,
    this.selectedLogNodeId,
    this.nodeQuickResults = const {},
    this.graphEpoch,
    required this.onRun,
    required this.onSelectNode,
    required this.onQuickTest,
    required this.onAddAfter,
    required this.onDelete,
  });

  final Map<String, dynamic> graph;
  final Map<String, dynamic>? execution;
  final bool executing;
  final String? selectedLogNodeId;
  final Map<String, Map<String, dynamic>> nodeQuickResults;
  final Object? graphEpoch;
  final VoidCallback onRun;
  final ValueChanged<String> onSelectNode;
  final ValueChanged<String> onQuickTest;
  final ValueChanged<String> onAddAfter;
  final ValueChanged<String> onDelete;

  @override
  State<FlowCanvas> createState() => _FlowCanvasState();
}

class _FlowCanvasState extends State<FlowCanvas> {
  late FlowController<FlowNodeData, void> _controller;
  String? _loadedFor;
  Object? _epoch;

  @override
  void initState() {
    super.initState();
    _controller = FlowController<FlowNodeData, void>();
    _rebuildGraph();
  }

  @override
  void didUpdateWidget(covariant FlowCanvas oldWidget) {
    super.didUpdateWidget(oldWidget);
    final gid = '${widget.graph['id']}';
    final epochChanged = widget.graphEpoch != _epoch;
    if (gid != _loadedFor || epochChanged) {
      _rebuildGraph();
    } else {
      _applyExecutionStatus();
      _applyQuickResults();
    }
  }

  void _rebuildGraph() {
    _controller.dispose();
    _controller = FlowController<FlowNodeData, void>();
    _loadedFor = '${widget.graph['id']}';
    _epoch = widget.graphEpoch;
    final nodes = widget.graph['nodes'];
    if (nodes is List) {
      for (final raw in nodes) {
        if (raw is! Map) continue;
        final id = '${raw['id']}';
        final stepName = id.contains('::') ? id.split('::').last : id;
        final labelRaw = '${raw['label'] ?? ''}';
        final label = (labelRaw.isEmpty || labelRaw == id) ? stepName : labelRaw;
        final x = (raw['x'] is num) ? (raw['x'] as num).toDouble() : 80.0;
        final y = (raw['y'] is num) ? (raw['y'] as num).toDouble() : 120.0;
        final kind = '${raw['kind'] ?? 'call_tool'}';
        final isTrigger =
            kind == 'manual_trigger' || id == '__manual_trigger__';
        final pathHint = '${raw['path'] ?? raw['exact_path'] ?? raw['path_contains'] ?? ''}';
        final quick = widget.nodeQuickResults[id];
        _controller.addNode(
          FlowNode<FlowNodeData>(
            id: id,
            type: isTrigger ? 'trigger' : 'api',
            data: FlowNodeData(
              id: id,
              label: isTrigger ? 'Manual Trigger' : label,
              kind: kind,
              method: isTrigger
                  ? 'START'
                  : '${raw['method'] ?? 'GET'}'.toUpperCase(),
              path: isTrigger ? 'click to run' : pathHint,
              service: '${raw['service'] ?? ''}',
              optional: raw['optional'] == true,
              status: quick?['status']?.toString(),
              httpStatus: quick?['http_status'] is int
                  ? quick!['http_status'] as int
                  : int.tryParse('${quick?['http_status'] ?? ''}'),
              quickRequest: quick?['request'],
              quickResponse: quick?['response'],
              quickError: quick?['error'],
              quickTesting: quick?['quickTesting'] == true,
            ),
            position: GraphPosition(Offset(x, y)),
            ports: isTrigger
                ? const [
                    FlowPort(
                      id: 'out',
                      side: PortSide.right,
                      kind: PortKind.output,
                    ),
                  ]
                : const [
                    FlowPort(
                      id: 'in',
                      side: PortSide.left,
                      kind: PortKind.input,
                    ),
                    FlowPort(
                      id: 'out',
                      side: PortSide.right,
                      kind: PortKind.output,
                    ),
                  ],
          ),
        );
      }
    }
    final edges = widget.graph['edges'];
    if (edges is List) {
      for (final raw in edges) {
        if (raw is! Map) continue;
        final from = '${raw['from']}';
        final to = '${raw['to']}';
        final eid = '${raw['id'] ?? '$from->$to'}';
        _controller.addEdge(
          FlowEdge<void>(
            id: eid,
            sourceNodeId: from,
            sourcePortId: 'out',
            targetNodeId: to,
            targetPortId: 'in',
            accent: raw['trigger'] == true
                ? const Color(0xFF7B1FA2)
                : (raw['optional'] == true
                    ? const Color(0xFF9E9E9E)
                    : (raw['pack_join'] == true
                        ? const Color(0xFF00897B)
                        : null)),
          ),
        );
      }
    }
    _applyExecutionStatus();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _controller.fitView();
    });
  }

  void _applyQuickResults() {
    for (final entry in widget.nodeQuickResults.entries) {
      final nid = entry.key;
      final st = entry.value;
      _controller.updateNodeData(
        nid,
        (data) => data.copyWith(
          status: st['status']?.toString() ?? data.status,
          httpStatus: st['http_status'] is int
              ? st['http_status'] as int
              : int.tryParse('${st['http_status'] ?? ''}'),
          quickRequest: st['request'],
          quickResponse: st['response'],
          quickError: st['error'],
          quickTesting: st['quickTesting'] == true,
        ),
      );
    }
  }

  void _applyExecutionStatus() {
    final nodes = widget.execution?['nodes'];
    if (nodes is! Map) return;
    for (final entry in nodes.entries) {
      final nid = '${entry.key}';
      final st = entry.value;
      if (st is! Map) continue;
      // Prefer quick-test overlay when present
      if (widget.nodeQuickResults.containsKey(nid)) continue;
      final req = st['request'];
      _controller.updateNodeData(
        nid,
        (data) => data.copyWith(
          status: '${st['status'] ?? ''}',
          httpStatus: st['http_status'] is int
              ? st['http_status'] as int
              : int.tryParse('${st['http_status'] ?? ''}'),
          quickRequest: req,
          quickResponse: st['response'],
          quickError: st['error'],
        ),
      );
      final status = '${st['status'] ?? ''}';
      Color? accent;
      if (status == 'ok') accent = const Color(0xFF2E7D32);
      if (status == 'fail') accent = const Color(0xFFC62828);
      if (status == 'running') accent = const Color(0xFF1565C0);
      if (status == 'skipped') accent = const Color(0xFF757575);
      if (accent != null) {
        for (final e in _controller.edges) {
          if (e.sourceNodeId == nid || e.targetNodeId == nid) {
            _controller.setEdgeAccent(e.id, accent);
          }
        }
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final theme = isDark
        ? const FlowTheme.dark()
        : FlowTheme(
            background: scheme.surface,
            gridDot: scheme.outlineVariant.withValues(alpha: 0.45),
            edge: scheme.primary.withValues(alpha: 0.7),
            edgeSelected: scheme.primary,
            selectionFill: scheme.primary.withValues(alpha: 0.12),
            selectionStroke: scheme.primary,
          );
    return NodeFlow<FlowNodeData, void>(
      controller: _controller,
      theme: theme,
      onNodeTap: (node) {
        if (node.data.isManualTrigger && !widget.executing) {
          widget.onRun();
          return;
        }
        widget.onSelectNode(node.id);
      },
      nodeBuilder: (context, node) => FlowNodeCard(
        data: node.data,
        busy: widget.executing,
        onTrigger: node.data.isManualTrigger && !widget.executing
            ? widget.onRun
            : null,
        onQuickTest: node.data.isManualTrigger
            ? null
            : () => widget.onQuickTest(node.id),
        onAdd: node.data.isManualTrigger
            ? null
            : () => widget.onAddAfter(node.id),
        onDelete: node.data.isManualTrigger
            ? null
            : () => widget.onDelete(node.id),
      ),
    );
  }
}
