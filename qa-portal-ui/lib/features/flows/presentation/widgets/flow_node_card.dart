import 'package:flutter/material.dart';

import 'json_preview.dart';

class FlowNodeData {
  const FlowNodeData({
    required this.id,
    required this.label,
    this.kind = 'call_tool',
    this.method = 'GET',
    this.path = '',
    this.service = '',
    this.optional = false,
    this.status,
    this.httpStatus,
    this.quickRequest,
    this.quickResponse,
    this.quickError,
    this.quickTesting = false,
    this.durationMs,
  });

  final String id;
  final String label;
  final String kind;
  final String method;
  final String path;
  final String service;
  final bool optional;
  final String? status;
  final int? httpStatus;
  final Object? quickRequest;
  final Object? quickResponse;
  final Object? quickError;
  final bool quickTesting;
  final double? durationMs;

  bool get isManualTrigger =>
      kind == 'manual_trigger' || id == '__manual_trigger__';

  bool get isComposeDraft => kind == 'compose' || id == '__compose_draft__';

  FlowNodeData copyWith({
    String? status,
    int? httpStatus,
    Object? quickRequest,
    Object? quickResponse,
    Object? quickError,
    bool? quickTesting,
    double? durationMs,
    bool clearQuick = false,
  }) {
    return FlowNodeData(
      id: id,
      label: label,
      kind: kind,
      method: method,
      path: path,
      service: service,
      optional: optional,
      status: status ?? this.status,
      httpStatus: httpStatus ?? this.httpStatus,
      quickRequest: clearQuick ? null : (quickRequest ?? this.quickRequest),
      quickResponse: clearQuick ? null : (quickResponse ?? this.quickResponse),
      quickError: clearQuick ? null : (quickError ?? this.quickError),
      quickTesting: quickTesting ?? this.quickTesting,
      durationMs: clearQuick ? null : (durationMs ?? this.durationMs),
    );
  }
}

class FlowNodeCard extends StatefulWidget {
  const FlowNodeCard({
    super.key,
    required this.data,
    this.busy = false,
    this.onTrigger,
    this.onQuickTest,
    this.onAdd,
    this.onDelete,
  });

  final FlowNodeData data;
  final bool busy;
  final VoidCallback? onTrigger;
  final VoidCallback? onQuickTest;
  final VoidCallback? onAdd;
  final VoidCallback? onDelete;

  @override
  State<FlowNodeCard> createState() => _FlowNodeCardState();
}

class _FlowNodeCardState extends State<FlowNodeCard>
    with SingleTickerProviderStateMixin {
  var _expanded = false;
  var _hover = false;
  late final TabController _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  Color _statusColor(BuildContext context) {
    switch (widget.data.status) {
      case 'ok':
        return const Color(0xFF2E7D32);
      case 'fail':
        return const Color(0xFFC62828);
      case 'running':
        return const Color(0xFF1565C0);
      case 'skipped':
        return const Color(0xFF757575);
      default:
        return widget.data.isManualTrigger
            ? const Color(0xFF7B1FA2)
            : Theme.of(context).colorScheme.outlineVariant;
    }
  }

  Map<String, dynamic>? get _reqMap {
    final r = widget.data.quickRequest;
    if (r is Map) return Map<String, dynamic>.from(r);
    return null;
  }

  @override
  Widget build(BuildContext context) {
    if (widget.data.isManualTrigger) {
      return _buildTrigger(context);
    }
    final border = _statusColor(context);
    final req = _reqMap;
    final showPlus = _hover && widget.onAdd != null;
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: SizedBox(
        width: _expanded ? 320 : 240,
        height: _expanded ? 340 : null,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Card(
              elevation: 1,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
                side: BorderSide(
                  color: border,
                  width: widget.data.status != null || widget.data.quickTesting
                      ? 2
                      : 1,
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize:
                      _expanded ? MainAxisSize.max : MainAxisSize.min,
                  children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: Theme.of(context)
                                  .colorScheme
                                  .primary
                                  .withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              widget.data.method,
                              style: const TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          if (widget.data.optional) ...[
                            const SizedBox(width: 6),
                            Text(
                              'optional',
                              style: Theme.of(context).textTheme.labelSmall,
                            ),
                          ],
                          const Spacer(),
                          if (widget.data.quickTesting)
                            const SizedBox(
                              width: 12,
                              height: 12,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          else if (widget.data.status != null)
                            Text(
                              widget.data.httpStatus != null
                                  ? '${widget.data.status} ${widget.data.httpStatus}'
                                  : '${widget.data.status}',
                              style: TextStyle(
                                fontSize: 10,
                                color: border,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        widget.data.label,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      if (widget.data.service.isNotEmpty)
                        Text(
                          widget.data.service,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      if (widget.data.path.isNotEmpty)
                        Text(
                          widget.data.path,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                      if (widget.data.durationMs != null)
                        Text(
                          '${widget.data.durationMs!.toStringAsFixed(widget.data.durationMs! >= 100 ? 0 : 1)} ms',
                          style: Theme.of(context)
                              .textTheme
                              .labelSmall
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 2,
                        children: [
                          _NodeAction(
                            tooltip: _expanded
                                ? 'Collapse'
                                : 'Headers / body / response',
                            icon: _expanded
                                ? Icons.unfold_less
                                : Icons.unfold_more,
                            onPressed: () =>
                                setState(() => _expanded = !_expanded),
                          ),
                          _NodeAction(
                            tooltip: 'Quick test this node',
                            icon: Icons.bolt,
                            color: const Color(0xFFF9A825),
                            onPressed: widget.data.quickTesting ||
                                    widget.onQuickTest == null
                                ? null
                                : () {
                                    setState(() => _expanded = true);
                                    _tabs.animateTo(2);
                                    widget.onQuickTest!();
                                  },
                          ),
                          _NodeAction(
                            tooltip: 'Add step after',
                            icon: Icons.add_circle_outline,
                            color: Theme.of(context).colorScheme.primary,
                            onPressed: widget.onAdd,
                          ),
                          _NodeAction(
                            tooltip: 'Delete node',
                            icon: Icons.delete_outline,
                            color: Theme.of(context).colorScheme.error,
                            onPressed: widget.onDelete,
                          ),
                        ],
                      ),
                      if (_expanded) ...[
                        const Divider(height: 8),
                        TabBar(
                          controller: _tabs,
                          labelPadding: EdgeInsets.zero,
                          tabs: const [
                            Tab(text: 'Headers'),
                            Tab(text: 'Body'),
                            Tab(text: 'Response'),
                          ],
                        ),
                        Expanded(
                          child: TabBarView(
                            controller: _tabs,
                            children: [
                              JsonPreview(
                                value: req?['headers'],
                                emptyLabel: 'No headers yet — Quick test',
                                maxLines: 40,
                              ),
                              JsonPreview(
                                value: req?['body'],
                                emptyLabel: 'No body yet — Quick test',
                                maxLines: 40,
                              ),
                              JsonPreview(
                                value: widget.data.quickError ??
                                    widget.data.quickResponse,
                                emptyLabel: 'No response yet — Quick test',
                                maxLines: 40,
                              ),
                            ],
                          ),
                        ),
                      ],
                  ],
                ),
              ),
            ),
            if (showPlus)
              Positioned(
                right: -14,
                top: 0,
                bottom: 0,
                child: Center(
                  child: Material(
                    color: Theme.of(context).colorScheme.primary,
                    shape: const CircleBorder(),
                    elevation: 3,
                    child: InkWell(
                      customBorder: const CircleBorder(),
                      onTap: widget.onAdd,
                      child: const SizedBox(
                        width: 28,
                        height: 28,
                        child: Icon(Icons.add, size: 18, color: Colors.white),
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildTrigger(BuildContext context) {
    final border = _statusColor(context);
    final showPlus = _hover && widget.onAdd != null;
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: SizedBox(
        width: 200,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Material(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              elevation: 1,
              borderRadius: BorderRadius.circular(28),
              child: InkWell(
                borderRadius: BorderRadius.circular(28),
                onTap: widget.onTrigger,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(28),
                    border: Border.all(color: border, width: 2),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        widget.busy
                            ? Icons.hourglass_top
                            : Icons.play_circle_filled,
                        color: border,
                        size: 28,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              widget.data.label,
                              style:
                                  const TextStyle(fontWeight: FontWeight.w700),
                            ),
                            Text(
                              widget.busy
                                  ? 'running…'
                                  : (widget.onTrigger == null
                                      ? 'save to run'
                                      : 'click to start'),
                              style: Theme.of(context).textTheme.labelSmall,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            if (showPlus)
              Positioned(
                right: -14,
                top: 0,
                bottom: 0,
                child: Center(
                  child: Material(
                    color: Theme.of(context).colorScheme.primary,
                    shape: const CircleBorder(),
                    elevation: 3,
                    child: InkWell(
                      customBorder: const CircleBorder(),
                      onTap: widget.onAdd,
                      child: const SizedBox(
                        width: 28,
                        height: 28,
                        child: Icon(Icons.add, size: 18, color: Colors.white),
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _NodeAction extends StatelessWidget {
  const _NodeAction({
    required this.tooltip,
    required this.icon,
    this.onPressed,
    this.color,
  });

  final String tooltip;
  final IconData icon;
  final VoidCallback? onPressed;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: tooltip,
      visualDensity: VisualDensity.compact,
      padding: EdgeInsets.zero,
      constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
      iconSize: 18,
      onPressed: onPressed,
      icon: Icon(icon, color: onPressed == null ? null : color),
    );
  }
}
