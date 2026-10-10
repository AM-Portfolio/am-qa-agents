part of 'run_detail_page.dart';

/// Dense row-1 chrome: identity, status, meta, actions, obs menu.
class _RunDetailHeader extends StatelessWidget {
  const _RunDetailHeader({
    required this.runId,
    required this.run,
    required this.status,
    required this.isLive,
    required this.actionBusy,
    required this.grafana,
    this.error,
    required this.onRerun,
    required this.onDebug,
    required this.onStop,
    required this.onSaveConfig,
    required this.onExport,
    required this.onRefresh,
    required this.onLoadLogs,
  });

  final String runId;
  final Map<String, dynamic> run;
  final String status;
  final bool isLive;
  final bool actionBusy;
  final String grafana;
  final String? error;
  final VoidCallback onRerun;
  final VoidCallback onDebug;
  final VoidCallback onStop;
  final VoidCallback onSaveConfig;
  final VoidCallback onExport;
  final VoidCallback onRefresh;
  final Future<Map<String, dynamic>> Function() onLoadLogs;

  String get _shortId => runId.length > 8 ? runId.substring(0, 8) : runId;

  String get _meta {
    final type = '${run['test_type'] ?? ''}'.trim();
    final cfg = '${run['config_name'] ?? run['config_id'] ?? ''}'.trim();
    final svc = '${run['service'] ?? ''}'.trim();
    final env = '${run['environment'] ?? ''}'.trim();
    final parts = <String>[
      if (type.isNotEmpty) type,
      if (cfg.isNotEmpty) cfg,
      if (svc.isNotEmpty || env.isNotEmpty) '$svc/$env',
      'dataset ${_payloadSetVersionLabel(run)}',
    ];
    if (run['api_count'] != null ||
        run['api_pass_count'] != null ||
        run['api_fail_count'] != null) {
      parts.add(
        '${_isPlaywrightRun(run) ? 'Steps' : 'APIs'} ${run['api_count'] ?? '—'} · '
        '${run['api_pass_count'] ?? '—'}✓ / ${run['api_fail_count'] ?? '—'}✗',
      );
    }
    return parts.join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final statusLabel = status.isEmpty ? 'unknown' : status;
    final failed = run['passed'] == false && status != 'running';
    final passed = run['passed'] == true;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            IconButton(
              tooltip: 'Back to runs',
              visualDensity: VisualDensity.compact,
              onPressed: () => context.go(AppRoutes.runs),
              icon: const Icon(Icons.arrow_back),
            ),
            Text(
              'Run $_shortId',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
            IconButton(
              tooltip: 'Copy run id',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.copy, size: 16),
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: runId));
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Run id copied'),
                    duration: Duration(seconds: 1),
                  ),
                );
              },
            ),
            const SizedBox(width: 4),
            Chip(
              visualDensity: VisualDensity.compact,
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              label: Text(
                passed
                    ? 'passed'
                    : (failed ? 'failed' : statusLabel),
              ),
              avatar: Icon(
                passed
                    ? Icons.check
                    : (failed ? Icons.close : Icons.circle),
                size: 14,
                color: failed ? scheme.error : null,
              ),
              backgroundColor: (failed ? scheme.error : AppColors.primary)
                  .withValues(alpha: 0.12),
              padding: EdgeInsets.zero,
              labelPadding: const EdgeInsets.only(right: 8),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                _meta,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
            if (actionBusy)
              const Padding(
                padding: EdgeInsets.only(right: 4),
                child: SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            Flexible(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                reverse: true,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (grafana.isNotEmpty)
                      IconButton(
                        tooltip: 'Grafana',
                        visualDensity: VisualDensity.compact,
                        onPressed: actionBusy
                            ? null
                            : () => launchUrl(Uri.parse(grafana)),
                        icon: const Icon(Icons.insights, size: 20),
                      ),
                    if (isLive)
                      IconButton(
                        tooltip: 'Stop',
                        visualDensity: VisualDensity.compact,
                        onPressed: actionBusy ? null : onStop,
                        icon: const Icon(Icons.stop, size: 20),
                      )
                    else ...[
                      IconButton(
                        tooltip: 'Re-run',
                        visualDensity: VisualDensity.compact,
                        onPressed: actionBusy ? null : onRerun,
                        icon: const Icon(Icons.replay, size: 20),
                      ),
                      IconButton(
                        tooltip: 'Debug 1-call',
                        visualDensity: VisualDensity.compact,
                        onPressed: actionBusy ? null : onDebug,
                        icon: const Icon(Icons.bug_report, size: 20),
                      ),
                    ],
                    MenuAnchor(
                      builder: (context, controller, _) => IconButton(
                        tooltip: 'More',
                        visualDensity: VisualDensity.compact,
                        icon: const Icon(Icons.more_vert, size: 20),
                        onPressed: () {
                          if (controller.isOpen) {
                            controller.close();
                          } else {
                            controller.open();
                          }
                        },
                      ),
                      menuChildren: [
                        MenuItemButton(
                          leadingIcon: const Icon(Icons.save_as, size: 18),
                          onPressed: actionBusy ? null : onSaveConfig,
                          child: const Text('Save as config'),
                        ),
                        MenuItemButton(
                          leadingIcon: const Icon(Icons.code, size: 18),
                          onPressed: actionBusy ? null : onExport,
                          child: const Text('Export JSON'),
                        ),
                        MenuItemButton(
                          leadingIcon: const Icon(Icons.refresh, size: 18),
                          onPressed: actionBusy ? null : onRefresh,
                          child: const Text('Refresh'),
                        ),
                      ],
                    ),
                    ObservabilityAttach(
                      compact: true,
                      traceId: run['trace_id']?.toString(),
                      correlationId: run['correlation_id']?.toString(),
                      observabilityResources: run['observability_resources'] is Map
                          ? Map<String, dynamic>.from(
                              run['observability_resources'] as Map,
                            )
                          : null,
                      loadLogs: onLoadLogs,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
        if (error != null && error!.trim().isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(left: 48, top: 2),
            child: Tooltip(
              message: error!,
              child: Text(
                error!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: scheme.error,
                  fontSize: 12,
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// Dense APIs filter controls for the tab band.
class _ApisTabFilters extends StatefulWidget {
  const _ApisTabFilters({
    required this.failedOnly,
    required this.apiQuery,
    required this.rowCount,
    required this.onFailedOnly,
    required this.onQuery,
  });

  final bool failedOnly;
  final String apiQuery;
  final int rowCount;
  final ValueChanged<bool> onFailedOnly;
  final ValueChanged<String> onQuery;

  @override
  State<_ApisTabFilters> createState() => _ApisTabFiltersState();
}

class _ApisTabFiltersState extends State<_ApisTabFilters> {
  late final TextEditingController _qCtrl;

  @override
  void initState() {
    super.initState();
    _qCtrl = TextEditingController(text: widget.apiQuery);
  }

  @override
  void didUpdateWidget(covariant _ApisTabFilters oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.apiQuery != widget.apiQuery &&
        _qCtrl.text != widget.apiQuery) {
      _qCtrl.text = widget.apiQuery;
    }
  }

  @override
  void dispose() {
    _qCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: 200,
          height: 36,
          child: TextField(
            controller: _qCtrl,
            style: Theme.of(context).textTheme.bodySmall,
            decoration: InputDecoration(
              isDense: true,
              contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
              hintText: 'Search APIs…',
              prefixIcon: const Icon(Icons.search, size: 16),
              prefixIconConstraints: const BoxConstraints(minWidth: 32, minHeight: 32),
              border: const OutlineInputBorder(),
              suffixIcon: _qCtrl.text.isEmpty
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.clear, size: 14),
                      visualDensity: VisualDensity.compact,
                      onPressed: () {
                        _qCtrl.clear();
                        widget.onQuery('');
                        setState(() {});
                      },
                    ),
            ),
            onSubmitted: widget.onQuery,
            onChanged: (_) => setState(() {}),
          ),
        ),
        const SizedBox(width: 6),
        FilterChip(
          label: const Text('Failed only'),
          selected: widget.failedOnly,
          visualDensity: VisualDensity.compact,
          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          onSelected: widget.onFailedOnly,
        ),
        const SizedBox(width: 6),
        Text(
          '${widget.rowCount}',
          style: Theme.of(context).textTheme.labelSmall,
        ),
      ],
    );
  }
}
