part of 'run_detail_page.dart';

class _RunDetailView extends StatelessWidget {
  const _RunDetailView({required this.runId});

  final String runId;

  String _absUrl(PortalConfig cfg, String url) {
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    var path = url.startsWith('/') ? url : '/$url';
    final base = cfg.apiBase.replaceAll(RegExp(r'/$'), '');
    // Avoid /spt-poc + /spt-poc/api/... when server stored ROOT_PATH-prefixed paths
    final basePath = Uri.tryParse(base)?.path ?? '';
    if (basePath.isNotEmpty && basePath != '/' && path.startsWith(basePath)) {
      path = path.substring(basePath.length);
      if (!path.startsWith('/')) path = '/$path';
    }
    return '$base$path';
  }

  Future<void> _saveAsConfigDialog(BuildContext context) async {
    final nameCtrl = TextEditingController(text: 'from-run-${runId.substring(0, 8)}');
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Save as config'),
        content: SizedBox(
          width: 360,
          child: TextField(
            controller: nameCtrl,
            decoration: const InputDecoration(
              labelText: 'Config name',
              border: OutlineInputBorder(),
            ),
            autofocus: true,
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    final name = nameCtrl.text.trim();
    if (name.isEmpty) return;
    final out = await context.read<_RunDetailCubit>().saveAsConfig(name);
    if (!context.mounted) return;
    if (out != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Saved config ${out['name'] ?? out['id'] ?? name}')),
      );
    }
  }

  Future<void> _exportJsonDialog(BuildContext context) async {
    final data = await context.read<_RunDetailCubit>().exportRun();
    if (!context.mounted || data == null) return;
    final pretty = const JsonEncoder.withIndent('  ').convert(data);
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Export run JSON'),
        content: SizedBox(
          width: 640,
          height: 480,
          child: SingleChildScrollView(
            child: SelectableText(
              pretty,
              style: Theme.of(ctx).textTheme.bodySmall,
            ),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
        ],
      ),
    );
  }

  Future<void> _startRunAndGo(
    BuildContext context,
    Future<String?> Function() start,
  ) async {
    final newId = await start();
    if (!context.mounted || newId == null) return;
    context.go('/runs/$newId');
  }

  Future<void> _savePayloadDialog(BuildContext context, String apiId) async {
    final nameCtrl = TextEditingController(text: 'default');
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Save payload'),
        content: SizedBox(
          width: 360,
          child: TextField(
            controller: nameCtrl,
            decoration: const InputDecoration(
              labelText: 'Payload name',
              border: OutlineInputBorder(),
            ),
            autofocus: true,
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    final name = nameCtrl.text.trim();
    final out = await context.read<_RunDetailCubit>().savePayload(
          apiId,
          name: name.isEmpty ? null : name,
        );
    if (!context.mounted) return;
    if (out != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Saved ${out['name'] ?? 'payload'} v${out['version'] ?? ''}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final cfg = getIt<PortalConfig>();
    return Padding(
      padding: const EdgeInsets.all(16),
      child: BlocBuilder<_RunDetailCubit, _RunDetailState>(
        builder: (context, state) {
          if (state.loading && state.run.isEmpty) {
            return const Center(child: CircularProgressIndicator());
          }
          if (state.error != null && state.run.isEmpty) {
            return Center(child: Text(state.error!));
          }
          final run = state.run;
          final status = '${run['status'] ?? ''}';
          final live = run['live'];
          final liveMap = live is Map ? Map<String, dynamic>.from(live) : null;
          final grafana = '${run['grafana_url'] ?? ''}';
          final metrics = run['metrics'] is Map
              ? Map<String, dynamic>.from(run['metrics'] as Map)
              : null;
          final results = run['results'];
          final isLive = status == 'running' || status == 'pending';
          final cubit = context.read<_RunDetailCubit>();

          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      IconButton(
                        onPressed: () => context.go(AppRoutes.runs),
                        icon: const Icon(Icons.arrow_back),
                      ),
                      Expanded(
                        child: Text(
                          'Run ${runId.length > 8 ? runId.substring(0, 8) : runId}',
                          style: Theme.of(context).textTheme.headlineSmall,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      IconButton(
                        tooltip: 'Copy run id',
                        visualDensity: VisualDensity.compact,
                        icon: const Icon(Icons.copy, size: 18),
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
                      if (state.actionBusy)
                        const Padding(
                          padding: EdgeInsets.only(left: 4, right: 8),
                          child: SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        ),
                    ],
                  ),
                  Padding(
                    padding: const EdgeInsets.only(left: 48),
                    child: SelectableText(
                      runId,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            fontFamily: 'monospace',
                          ),
                      maxLines: 1,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      if (grafana.isNotEmpty)
                        OutlinedButton.icon(
                          onPressed: state.actionBusy
                              ? null
                              : () => launchUrl(Uri.parse(grafana)),
                          icon: const Icon(Icons.insights, size: 18),
                          label: const Text('Grafana'),
                        ),
                      if (isLive)
                        FilledButton.tonalIcon(
                          onPressed: state.actionBusy ? null : () => cubit.stop(),
                          icon: const Icon(Icons.stop),
                          label: const Text('Stop'),
                        )
                      else ...[
                        OutlinedButton.icon(
                          onPressed: state.actionBusy
                              ? null
                              : () => _startRunAndGo(context, cubit.rerun),
                          icon: const Icon(Icons.replay, size: 18),
                          label: const Text('Re-run'),
                        ),
                        OutlinedButton.icon(
                          onPressed: state.actionBusy
                              ? null
                              : () => _startRunAndGo(context, cubit.debugRun),
                          icon: const Icon(Icons.bug_report, size: 18),
                          label: const Text('Debug 1-call'),
                        ),
                      ],
                      OutlinedButton.icon(
                        onPressed:
                            state.actionBusy ? null : () => _saveAsConfigDialog(context),
                        icon: const Icon(Icons.save_as, size: 18),
                        label: const Text('Save as config'),
                      ),
                      OutlinedButton.icon(
                        onPressed:
                            state.actionBusy ? null : () => _exportJsonDialog(context),
                        icon: const Icon(Icons.code, size: 18),
                        label: const Text('Export JSON'),
                      ),
                      OutlinedButton.icon(
                        onPressed: state.actionBusy ? null : () => cubit.load(),
                        icon: const Icon(Icons.refresh, size: 18),
                        label: const Text('Refresh'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ObservabilityAttach(
                    traceId: run['trace_id']?.toString(),
                    correlationId: run['correlation_id']?.toString(),
                    observabilityResources: run['observability_resources'] is Map
                        ? Map<String, dynamic>.from(
                            run['observability_resources'] as Map,
                          )
                        : null,
                    loadLogs: () =>
                        context.read<_RunDetailCubit>().loadObsLogs(),
                  ),
                ],
              ),
              if (state.error != null && state.run.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  state.error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Chip(
                    label: Text(status.isEmpty ? 'unknown' : status),
                    backgroundColor: AppColors.primary.withValues(alpha: 0.12),
                  ),
                  Text(
                    '${run['test_type'] ?? ''} · '
                    '${run['config_name'] ?? run['config_id'] ?? ''} · '
                    '${run['service'] ?? ''}/${run['environment'] ?? ''}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (run['passed'] == true)
                    const Chip(label: Text('passed'), avatar: Icon(Icons.check, size: 16)),
                  if (run['passed'] == false && status != 'running')
                    Chip(
                      label: const Text('failed'),
                      avatar: Icon(Icons.close, size: 16, color: Theme.of(context).colorScheme.error),
                    ),
                  if (run['api_count'] != null ||
                      run['api_pass_count'] != null ||
                      run['api_fail_count'] != null)
                    Chip(
                      label: Text(
                        '${_isPlaywrightRun(run) ? 'Steps' : 'APIs'} ${run['api_count'] ?? '—'} · '
                        '${run['api_pass_count'] ?? '—'}✓ / ${run['api_fail_count'] ?? '—'}✗',
                      ),
                    ),
                ],
              ),
              if (liveMap != null) ...[
                const SizedBox(height: 8),
                LinearProgressIndicator(
                  value: liveMap['pct'] is num
                      ? (liveMap['pct'] as num).toDouble().clamp(0, 100) / 100
                      : null,
                ),
                const SizedBox(height: 4),
                Text(
                  '${liveMap['phase'] ?? ''} — ${liveMap['message'] ?? ''}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
              if (metrics != null && metrics.isNotEmpty) ...[
                const SizedBox(height: 8),
                Wrap(
                  spacing: 12,
                  children: [
                    for (final e in metrics.entries.take(8))
                      Chip(
                        label: Text('${e.key}: ${e.value}'),
                        visualDensity: VisualDensity.compact,
                      ),
                  ],
                ),
              ],
              const SizedBox(height: 12),
              Expanded(
                child: DefaultTabController(
                  length: 4,
                  child: Column(
                    children: [
                      TabBar(
                        isScrollable: true,
                        tabs: [
                          const Tab(text: 'Overview'),
                          const Tab(text: 'Inspector'),
                          const Tab(text: 'Artifacts'),
                          Tab(text: _isPlaywrightRun(run) ? 'Steps' : 'APIs'),
                        ],
                      ),
                      Expanded(
                        child: TabBarView(
                          children: [
                            _OverviewTab(
                              run: run,
                              results: results,
                              baseline: state.baseline,
                              apis: state.apis,
                              absUrl: (u) => _absUrl(cfg, u),
                            ),
                            _InspectorTab(
                              traces: state.traces.isEmpty ? state.apis : state.traces,
                              selected: state.selectedTrace,
                              selectedApiId: state.selectedTraceApiId,
                              failedOnly: state.failedOnly,
                              onFailedOnly: cubit.setFailedOnly,
                              onOpen: cubit.openTrace,
                              onSavePayload: (apiId) => _savePayloadDialog(context, apiId),
                              absUrl: (u) => _absUrl(cfg, u),
                            ),
                            _ArtifactsTab(
                              artifacts: state.artifacts,
                              absUrl: (u) => _absUrl(cfg, u),
                            ),
                            _ApisTab(apis: state.apis.isNotEmpty
                                ? state.apis
                                : _resultRows(run: run, results: results)),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
