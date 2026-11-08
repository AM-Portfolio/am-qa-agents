import 'package:flutter/material.dart';
import 'package:node_flow/node_flow.dart';

import 'graph_layout.dart';
import 'ui_step_node_card.dart';
import 'ui_step_node_data.dart';

/// Read/write NodeFlow canvas for UI step graphs.
class UiStepFlowCanvas extends StatefulWidget {
  const UiStepFlowCanvas({
    super.key,
    required this.graph,
    this.evidenceByNodeId = const {},
    this.selectedNodeId,
    this.graphEpoch,
    this.readOnly = false,
    this.onSelectNode,
    this.onRun,
    this.onAddAfter,
    this.onDelete,
    this.onOpenInRun,
    this.resolveScreenshotUrl,
  });

  final Map<String, dynamic> graph;
  final Map<String, Map<String, dynamic>> evidenceByNodeId;
  final String? selectedNodeId;
  final Object? graphEpoch;
  final bool readOnly;
  final ValueChanged<String>? onSelectNode;
  final VoidCallback? onRun;
  final ValueChanged<String>? onAddAfter;
  final ValueChanged<String>? onDelete;
  final ValueChanged<String>? onOpenInRun;
  final String Function(String url)? resolveScreenshotUrl;

  @override
  State<UiStepFlowCanvas> createState() => _UiStepFlowCanvasState();
}

class _UiStepFlowCanvasState extends State<UiStepFlowCanvas> {
  late FlowController<UiStepNodeData, void> _controller;
  String? _loadedFor;
  Object? _epoch;

  @override
  void initState() {
    super.initState();
    _controller = FlowController<UiStepNodeData, void>();
    _rebuildGraph();
  }

  @override
  void didUpdateWidget(covariant UiStepFlowCanvas oldWidget) {
    super.didUpdateWidget(oldWidget);
    final gid = '${widget.graph['id']}';
    final epochChanged = widget.graphEpoch != _epoch;
    if (gid != _loadedFor || epochChanged) {
      _rebuildGraph();
    } else {
      _applyEvidence();
      _applySelection();
    }
  }

  String? _peek(Object? value) {
    if (value == null) return null;
    if (value is String) {
      final t = value.trim();
      if (t.isEmpty) return null;
      return t.length > 48 ? '${t.substring(0, 48)}…' : t;
    }
    if (value is Map) {
      final body = value['body'];
      if (body != null) return _peek(body);
      final s = value.toString();
      return s.length > 48 ? '${s.substring(0, 48)}…' : s;
    }
    final s = '$value';
    return s.length > 48 ? '${s.substring(0, 48)}…' : s;
  }

  UiStepNodeData _dataFor(Map raw, {required int index}) {
    final id = '${raw['id']}';
    final kind = '${raw['kind'] ?? 'ui_step'}';
    final isTrigger = kind == 'manual_trigger' || id == kManualTriggerId;
    final labelRaw = '${raw['label'] ?? ''}';
    final label = labelRaw.isEmpty
        ? (isTrigger ? 'Start' : id)
        : labelRaw;
    final ev = widget.evidenceByNodeId[id];
    var shot = ev?['screenshot_url']?.toString();
    if (shot != null &&
        shot.isNotEmpty &&
        widget.resolveScreenshotUrl != null) {
      shot = widget.resolveScreenshotUrl!(shot);
    }
    final dur = durationMsFrom(ev) ??
        (raw['duration_ms'] is num
            ? (raw['duration_ms'] as num).toDouble()
            : null);
    String? status = ev?['status']?.toString();
    if (status == null || status.isEmpty) {
      final passed = ev?['checks_passed'];
      if (passed == true) status = 'ok';
      if (passed == false) status = 'fail';
    }
    return UiStepNodeData(
      id: id,
      label: label,
      kind: kind,
      method: isTrigger
          ? 'START'
          : '${raw['method'] ?? (kind == 'verification' ? 'VERIFY' : 'STEP')}'
              .toUpperCase(),
      status: status,
      durationMs: dur,
      screenshotUrl: shot,
      requestPeek: _peek(ev?['request']),
      responsePeek: _peek(ev?['response'] ?? ev?['error']),
      selected: widget.selectedNodeId == id,
    );
  }

  void _rebuildGraph() {
    _controller.dispose();
    _controller = FlowController<UiStepNodeData, void>();
    _loadedFor = '${widget.graph['id']}';
    _epoch = widget.graphEpoch;
    final nodes = widget.graph['nodes'];
    var index = 0;
    if (nodes is List) {
      for (final raw in nodes) {
        if (raw is! Map) continue;
        final id = '${raw['id']}';
        final kind = '${raw['kind'] ?? 'ui_step'}';
        final isTrigger = kind == 'manual_trigger' || id == kManualTriggerId;
        final x = (raw['x'] is num)
            ? (raw['x'] as num).toDouble()
            : defaultNodeX(index);
        final y = (raw['y'] is num)
            ? (raw['y'] as num).toDouble()
            : defaultNodeY(index);
        _controller.addNode(
          FlowNode<UiStepNodeData>(
            id: id,
            type: isTrigger ? 'trigger' : 'ui',
            data: _dataFor(raw, index: index),
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
        index++;
      }
    }
    final edges = widget.graph['edges'];
    if (edges is List) {
      for (final raw in edges) {
        if (raw is! Map) continue;
        final from = '${raw['from']}';
        final to = '${raw['to']}';
        final eid = '${raw['id'] ?? '$from->$to'}';
        final toEv = widget.evidenceByNodeId[to];
        final accent = statusEdgeAccent(toEv?['status']?.toString()) ??
            (toEv?['checks_passed'] == true
                ? statusEdgeAccent('ok')
                : (toEv?['checks_passed'] == false
                    ? statusEdgeAccent('fail')
                    : (raw['trigger'] == true
                        ? const Color(0xFF7B1FA2)
                        : null)));
        _controller.addEdge(
          FlowEdge<void>(
            id: eid,
            sourceNodeId: from,
            sourcePortId: 'out',
            targetNodeId: to,
            targetPortId: 'in',
            accent: accent,
          ),
        );
      }
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _controller.fitView();
    });
  }

  void _applyEvidence() {
    for (final n in _controller.nodes) {
      final nid = n.id;
      final ev = widget.evidenceByNodeId[nid];
      if (ev == null) {
        _controller.updateNodeData(
          nid,
          (data) => data.copyWith(
            clearEvidence: true,
            selected: widget.selectedNodeId == nid,
          ),
        );
        for (final e in _controller.edges) {
          if (e.targetNodeId == nid) {
            _controller.setEdgeAccent(e.id, null);
          }
        }
        continue;
      }
      var shot = ev['screenshot_url']?.toString();
      if (shot != null &&
          shot.isNotEmpty &&
          widget.resolveScreenshotUrl != null) {
        shot = widget.resolveScreenshotUrl!(shot);
      }
      String? status = ev['status']?.toString();
      if (status == null || status.isEmpty) {
        if (ev['checks_passed'] == true) status = 'ok';
        if (ev['checks_passed'] == false) status = 'fail';
      }
      final clear = status == null || status.isEmpty;
      _controller.updateNodeData(
        nid,
        (data) => data.copyWith(
          clearEvidence: clear,
          status: clear ? null : status,
          durationMs: durationMsFrom(ev),
          screenshotUrl: shot,
          requestPeek: _peek(ev['request']),
          responsePeek: _peek(ev['response'] ?? ev['error']),
          selected: widget.selectedNodeId == nid,
        ),
      );
      final accent = statusEdgeAccent(status);
      for (final e in _controller.edges) {
        if (e.targetNodeId == nid) {
          _controller.setEdgeAccent(e.id, accent);
        }
      }
    }
  }

  void _applySelection() {
    for (final n in _controller.nodes) {
      final selected = widget.selectedNodeId == n.id;
      if (n.data.selected != selected) {
        _controller.updateNodeData(
          n.id,
          (data) => data.copyWith(selected: selected),
        );
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
    return NodeFlow<UiStepNodeData, void>(
      controller: _controller,
      theme: theme,
      onNodeTap: (node) {
        if (node.data.isManualTrigger &&
            !widget.readOnly &&
            widget.onRun != null) {
          widget.onRun!();
          return;
        }
        widget.onSelectNode?.call(node.id);
      },
      nodeBuilder: (context, node) => UiStepNodeCard(
        data: node.data,
        readOnly: widget.readOnly,
        onTrigger: node.data.isManualTrigger && !widget.readOnly
            ? widget.onRun
            : null,
        onAdd: widget.readOnly || node.data.isManualTrigger
            ? null
            : () => widget.onAddAfter?.call(node.id),
        onDelete: widget.readOnly || node.data.isManualTrigger
            ? null
            : () => widget.onDelete?.call(node.id),
        onOpenInRun: widget.onOpenInRun == null
            ? null
            : () => widget.onOpenInRun!(node.id),
      ),
    );
  }
}
