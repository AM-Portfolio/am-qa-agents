part of 'run_detail_page.dart';

class _InspectorTab extends StatefulWidget {
  const _InspectorTab({
    required this.traces,
    required this.selected,
    required this.selectedApiId,
    required this.failedOnly,
    required this.onFailedOnly,
    required this.onOpen,
    required this.onSavePayload,
    required this.absUrl,
  });

  final List<Map<String, dynamic>> traces;
  final Map<String, dynamic>? selected;
  final String? selectedApiId;
  final bool failedOnly;
  final ValueChanged<bool> onFailedOnly;
  final ValueChanged<Map<String, dynamic>> onOpen;
  final Future<void> Function(String apiId) onSavePayload;
  final String Function(String) absUrl;

  @override
  State<_InspectorTab> createState() => _InspectorTabState();
}

class _InspectorTabState extends State<_InspectorTab> {
  var _graphMode = false;

  bool get _hasUiSteps =>
      widget.traces.any((t) => '${t['kind'] ?? ''}' == 'ui_step');

  @override
  void initState() {
    super.initState();
    _graphMode = _hasUiSteps;
  }

  @override
  void didUpdateWidget(covariant _InspectorTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!_hasUiSteps && _graphMode) {
      _graphMode = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final traces = widget.traces;
    final selected = widget.selected;
    final failedOnly = widget.failedOnly;
    final onFailedOnly = widget.onFailedOnly;
    final onOpen = widget.onOpen;
    final graph = _hasUiSteps ? uiRunGraphFromTraces(traces) : null;
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            flex: 2,
            child: GlassCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: [
                  Container(
                    padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
                    decoration: BoxDecoration(
                      border: Border(
                        bottom: BorderSide(
                          color: scheme.outlineVariant.withValues(alpha: 0.5),
                        ),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Row(
                          children: [
                            Text(
                              _graphMode ? 'Graph' : 'Calls',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleSmall
                                  ?.copyWith(fontWeight: FontWeight.w700),
                            ),
                            const Spacer(),
                            if (_hasUiSteps)
                              SegmentedButton<bool>(
                                segments: const [
                                  ButtonSegment(
                                    value: true,
                                    label: Text('Graph'),
                                    icon: Icon(Icons.account_tree, size: 16),
                                  ),
                                  ButtonSegment(
                                    value: false,
                                    label: Text('List'),
                                    icon: Icon(Icons.list, size: 16),
                                  ),
                                ],
                                selected: {_graphMode},
                                onSelectionChanged: (s) =>
                                    setState(() => _graphMode = s.first),
                                style: const ButtonStyle(
                                  visualDensity: VisualDensity.compact,
                                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                ),
                              ),
                            if (!_graphMode) ...[
                              const SizedBox(width: 8),
                              FilterChip(
                                label: const Text('Failed only'),
                                selected: failedOnly,
                                onSelected: onFailedOnly,
                                visualDensity: VisualDensity.compact,
                              ),
                            ],
                          ],
                        ),
                        if (_graphMode && graph != null) ...[
                          const SizedBox(height: 6),
                          Wrap(
                            spacing: 8,
                            runSpacing: 4,
                            children: [
                              Chip(
                                label: Text(
                                  'Total ${graph.totalLatencyMs.toStringAsFixed(0)} ms',
                                ),
                                visualDensity: VisualDensity.compact,
                              ),
                              Chip(
                                label: Text('Pass ${graph.passCount}'),
                                visualDensity: VisualDensity.compact,
                              ),
                              Chip(
                                label: Text('Fail ${graph.failCount}'),
                                visualDensity: VisualDensity.compact,
                              ),
                            ],
                          ),
                        ],
                      ],
                    ),
                  ),
                  Expanded(
                    child: traces.isEmpty
                        ? const Center(child: Text('No traces yet'))
                        : _graphMode && graph != null
                            ? UiStepFlowCanvas(
                                graph: graph.graph,
                                evidenceByNodeId: graph.evidence,
                                readOnly: true,
                                selectedNodeId:
                                    selected?['api_id']?.toString(),
                                graphEpoch: Object.hash(
                                  traces.length,
                                  selected?['api_id'],
                                  graph.totalLatencyMs,
                                ),
                                resolveScreenshotUrl: widget.absUrl,
                                onSelectNode: (nodeId) {
                                  final t = traceForNodeId(
                                    graph.evidence,
                                    nodeId,
                                  );
                                  if (t != null) onOpen(t);
                                },
                              )
                        : ListView.separated(
                            itemCount: traces.length,
                            separatorBuilder: (_, __) => Divider(
                              height: 1,
                              color: scheme.outlineVariant.withValues(alpha: 0.35),
                            ),
                            itemBuilder: (context, i) {
                              final t = traces[i];
                              final isUi = '${t['kind'] ?? ''}' == 'ui_step';
                              final method = (_nonEmpty(t['method']) ?? 'HTTP').toUpperCase();
                              final endpoint = isUi
                                  ? '${t['call_index'] ?? i + 1}. ${t['name'] ?? method}'
                                  : _endpointLabel(t);
                              final fullUrl = _traceUrl(t);
                              final statusCode = _traceStatus(t);
                              final failed = _traceFailed(t);
                              final selectedHere = identical(selected, t) ||
                                  (selected != null &&
                                      selected['call_index'] == t['call_index'] &&
                                      selected['api_id'] == t['api_id']);
                              final ms = t['timings'] is Map
                                  ? (t['timings'] as Map)['duration_ms']
                                  : (t['duration_ms'] ?? t['latency_ms']);
                              return Material(
                                color: selectedHere
                                    ? AppColors.primary.withValues(alpha: 0.10)
                                    : Colors.transparent,
                                child: InkWell(
                                  onTap: () => onOpen(t),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 12,
                                      vertical: 10,
                                    ),
                                    child: Row(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Container(
                                          constraints: const BoxConstraints(minWidth: 52),
                                          padding: const EdgeInsets.symmetric(
                                            horizontal: 8,
                                            vertical: 5,
                                          ),
                                          decoration: BoxDecoration(
                                            color: (failed
                                                    ? scheme.error
                                                    : AppColors.primary)
                                                .withValues(alpha: 0.12),
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Text(
                                            isUi ? 'UI' : method,
                                            textAlign: TextAlign.center,
                                            style: TextStyle(
                                              fontSize: 11,
                                              fontWeight: FontWeight.w800,
                                              color: failed ? scheme.error : AppColors.primary,
                                            ),
                                          ),
                                        ),
                                        const SizedBox(width: 10),
                                        Expanded(
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Text(
                                                endpoint,
                                                maxLines: 2,
                                                overflow: TextOverflow.ellipsis,
                                                style: const TextStyle(
                                                  fontWeight: FontWeight.w700,
                                                  fontSize: 13,
                                                  height: 1.25,
                                                ),
                                              ),
                                              if (!isUi &&
                                                  fullUrl.isNotEmpty &&
                                                  fullUrl != endpoint) ...[
                                                const SizedBox(height: 2),
                                                Text(
                                                  fullUrl,
                                                  maxLines: 1,
                                                  overflow: TextOverflow.ellipsis,
                                                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                                        fontSize: 11,
                                                        color: scheme.onSurface.withValues(alpha: 0.55),
                                                      ),
                                                ),
                                              ],
                                              const SizedBox(height: 4),
                                              Text(
                                                [
                                                  if (statusCode != null) '$statusCode',
                                                  if (ms != null) '${ms}ms',
                                                  failed ? 'FAIL' : 'PASS',
                                                ].join(' · '),
                                                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                                      fontWeight: FontWeight.w600,
                                                      color: failed
                                                          ? scheme.error
                                                          : Colors.green.shade700,
                                                    ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            flex: 3,
            child: GlassCard(
              padding: EdgeInsets.zero,
              child: selected == null
                  ? Center(
                      child: Text(
                        'Select a call to inspect request / response',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: scheme.onSurface.withValues(alpha: 0.55),
                            ),
                      ),
                    )
                  : _TraceDetailPanel(
                      trace: selected,
                      apiId: widget.selectedApiId,
                      onSavePayload: widget.onSavePayload,
                      absUrl: widget.absUrl,
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

