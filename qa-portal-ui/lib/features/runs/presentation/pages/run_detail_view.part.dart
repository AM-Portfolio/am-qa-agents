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
          final results = run['results'];
          final isLive = status == 'running' || status == 'pending';
          final cubit = context.read<_RunDetailCubit>();
          final apiRows = state.apis.isNotEmpty
              ? state.apis
              : _resultRows(run: run, results: results);

          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _RunDetailHeader(
                runId: runId,
                run: run,
                status: status,
                isLive: isLive,
                actionBusy: state.actionBusy,
                grafana: grafana,
                error: state.run.isNotEmpty ? state.error : null,
                onRerun: () => _startRunAndGo(context, cubit.rerun),
                onDebug: () => _startRunAndGo(context, cubit.debugRun),
                onStop: cubit.stop,
                onSaveConfig: () => _saveAsConfigDialog(context),
                onExport: () => _exportJsonDialog(context),
                onRefresh: cubit.load,
                onLoadLogs: cubit.loadObsLogs,
              ),
              if (isLive && liveMap != null) ...[
                const SizedBox(height: 4),
                LinearProgressIndicator(
                  value: liveMap['pct'] is num
                      ? (liveMap['pct'] as num).toDouble().clamp(0, 100) / 100
                      : null,
                ),
                Text(
                  '${liveMap['phase'] ?? ''} — ${liveMap['message'] ?? ''}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              ],
              const SizedBox(height: 4),
              Expanded(
                child: DefaultTabController(
                  length: 3,
                  child: Builder(
                    builder: (context) {
                      final tabCtrl = DefaultTabController.of(context);
                      return AnimatedBuilder(
                        animation: tabCtrl,
                        builder: (context, _) {
                          final onInspector = tabCtrl.index == 1;
                          return Column(
                            children: [
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.center,
                                children: [
                                  Flexible(
                                    child: TabBar(
                                      isScrollable: true,
                                      tabs: [
                                        const Tab(text: 'Overview'),
                                        const Tab(text: 'Inspector'),
                                        Tab(
                                          text: state.artifacts.isEmpty
                                              ? 'Artifacts'
                                              : 'Artifacts (${state.artifacts.length})',
                                        ),
                                      ],
                                    ),
                                  ),
                                  if (onInspector)
                                    Flexible(
                                      child: SingleChildScrollView(
                                        scrollDirection: Axis.horizontal,
                                        reverse: true,
                                        padding: const EdgeInsets.only(left: 8),
                                        child: _ApisTabFilters(
                                          failedOnly: state.failedOnly,
                                          apiQuery: state.apiQuery,
                                          rowCount: apiRows.length,
                                          onFailedOnly: cubit.setFailedOnly,
                                          onQuery: cubit.setApiQuery,
                                        ),
                                      ),
                                    ),
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
                                    _ApisTab(
                                      run: run,
                                      apis: apiRows,
                                      selected: state.selectedApi,
                                      showTry: state.showApiTry,
                                      onSelect: cubit.selectApi,
                                      onShowTry: cubit.setShowApiTry,
                                    ),
                                    _ArtifactsTab(
                                      artifacts: state.artifacts,
                                      absUrl: (u) => _absUrl(cfg, u),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          );
                        },
                      );
                    },
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
