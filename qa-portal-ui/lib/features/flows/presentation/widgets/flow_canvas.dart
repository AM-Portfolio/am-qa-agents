import 'package:flutter/material.dart';
import 'package:node_flow/node_flow.dart';

import 'flow_node_card.dart';
import 'flow_node_compose_card.dart';

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
    required this.onCommitAdd,
    required this.onDelete,
    required this.listTools,
    required this.listServices,
    required this.loadPayloadSet,
    this.defaultService = '',
    this.autoOpenCompose = false,
    this.allowRun = true,
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
  final void Function(String afterNodeId, Map<String, dynamic> stub)
      onCommitAdd;
  final ValueChanged<String> onDelete;
  final Future<List<Map<String, dynamic>>> Function(String service) listTools;
  final Future<List<String>> Function() listServices;
  final Future<Map<String, dynamic>?> Function(String service, {int? version})
      loadPayloadSet;
  final String defaultService;
  /// When true and the graph has only a Manual Trigger, open Add-step beside it.
  final bool autoOpenCompose;
  final bool allowRun;

  @override
  State<FlowCanvas> createState() => _FlowCanvasState();
}

class _FlowCanvasState extends State<FlowCanvas> {
  static const _composeId = '__compose_draft__';
  static const _composeEdgeId = '__compose_draft_edge__';

  late FlowController<FlowNodeData, void> _controller;
  String? _loadedFor;
  Object? _epoch;
  String? _composeAfterId;
  String _composeInitialService = '';

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
      _composeAfterId = null;
      _rebuildGraph();
    } else {
      _applyExecutionStatus();
      _applyQuickResults();
    }
  }

  void _dismissCompose() {
    if (_composeAfterId == null) return;
    _controller.removeNode(_composeId);
    _composeAfterId = null;
    _composeInitialService = '';
  }

  void _openCompose(String afterId) {
    if (_composeAfterId == afterId) {
      setState(_dismissCompose);
      return;
    }
    final src = _controller.getNode(afterId);
    if (src == null) return;

    _dismissCompose();

    var svc = src.data.service.trim();
    if (svc.isEmpty) svc = widget.defaultService.trim();

    final origin = src.position.value.offset;
    // Seed sizes so port anchors match the rendered cards (default 256×100
    // leaves the Manual Trigger output floating past the pill).
    final srcW = src.measuredSize.value.width;
    final gap = 48.0;
    _controller.addNode(
      FlowNode<FlowNodeData>(
        id: _composeId,
        type: 'compose',
        data: FlowNodeData(
          id: _composeId,
          label: 'Add step',
          kind: 'compose',
          method: 'NEW',
          path: '',
          service: svc,
        ),
        position: GraphPosition.fromXY(origin.dx + srcW + gap, origin.dy),
        size: const Size(320, 420),
        ports: const [
          FlowPort(
            id: 'in',
            side: PortSide.left,
            kind: PortKind.input,
          ),
        ],
      ),
    );
    _controller.addEdge(
      FlowEdge<void>(
        id: _composeEdgeId,
        sourceNodeId: afterId,
        sourcePortId: 'out',
        targetNodeId: _composeId,
        targetPortId: 'in',
        accent: const Color(0xFF7B1FA2),
      ),
    );
    setState(() {
      _composeAfterId = afterId;
      _composeInitialService = svc;
    });
  }

  void _confirmCompose(Map<String, dynamic> stub) {
    final afterId = _composeAfterId;
    if (afterId == null) return;
    setState(_dismissCompose);
    widget.onCommitAdd(afterId, stub);
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
              durationMs: quick?['duration_ms'] is num
                  ? (quick!['duration_ms'] as num).toDouble()
                  : double.tryParse('${quick?['duration_ms'] ?? ''}'),
            ),
            position: GraphPosition(Offset(x, y)),
            // Match FlowNodeCard / trigger pill so the out-port sits on the edge.
            size: isTrigger
                ? const Size(200, 56)
                : const Size(240, 120),
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
      if (!mounted) return;
      _controller.fitView();
      // Wait one more frame so trigger size is measured before wiring compose.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _maybeAutoOpenCompose();
      });
    });
  }

  void _maybeAutoOpenCompose() {
    if (!widget.autoOpenCompose) return;
    if (_composeAfterId != null) return;
    var apiCount = 0;
    for (final n in _controller.nodes) {
      if (!n.data.isManualTrigger && !n.data.isComposeDraft) apiCount++;
    }
    if (apiCount > 0) return;
    if (_controller.getNode('__manual_trigger__') == null) return;
    _openCompose('__manual_trigger__');
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
          durationMs: st['duration_ms'] is num
              ? (st['duration_ms'] as num).toDouble()
              : double.tryParse('${st['duration_ms'] ?? ''}'),
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
          durationMs: st['duration_ms'] is num
              ? (st['duration_ms'] as num).toDouble()
              : double.tryParse('${st['duration_ms'] ?? ''}'),
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
        if (node.data.isComposeDraft) return;
        if (node.data.isManualTrigger &&
            widget.allowRun &&
            !widget.executing) {
          widget.onRun();
          return;
        }
        widget.onSelectNode(node.id);
      },
      nodeBuilder: (context, node) {
        if (node.data.isComposeDraft) {
          return FlowNodeComposeCard(
            key: ValueKey('compose-$_composeAfterId-$_composeInitialService'),
            listTools: widget.listTools,
            listServices: widget.listServices,
            loadPayloadSet: widget.loadPayloadSet,
            initialService: _composeInitialService,
            onCancel: () => setState(_dismissCompose),
            onConfirm: _confirmCompose,
          );
        }
        return FlowNodeCard(
          data: node.data,
          busy: widget.executing,
          onTrigger: node.data.isManualTrigger &&
                  widget.allowRun &&
                  !widget.executing
              ? widget.onRun
              : null,
          onQuickTest: node.data.isManualTrigger || !widget.allowRun
              ? null
              : () => widget.onQuickTest(node.id),
          onAdd: () => _openCompose(node.id),
          onDelete: node.data.isManualTrigger
              ? null
              : () => widget.onDelete(node.id),
        );
      },
    );
  }
}
