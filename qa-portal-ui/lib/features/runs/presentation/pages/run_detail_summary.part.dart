part of 'run_detail_page.dart';

class _OverviewTab extends StatelessWidget {
  const _OverviewTab({
    required this.run,
    this.results,
    this.baseline,
    this.apis = const [],
    required this.absUrl,
  });

  final Map<String, dynamic> run;
  final Object? results;
  final Map<String, dynamic>? baseline;
  final List<Map<String, dynamic>> apis;
  final String Function(String) absUrl;

  String _shortTs(dynamic v) {
    final s = '$v'.trim();
    if (s.isEmpty || s == 'null') return '—';
    // 2026-10-09T23:45:09.647024+00:00 → 2026-10-09 23:45
    if (s.length >= 16 && s.contains('T')) {
      return '${s.substring(0, 10)} ${s.substring(11, 16)}';
    }
    return s;
  }

  @override
  Widget build(BuildContext context) {
    final params = _runParams(run);
    final metrics = run['metrics_summary'] is Map
        ? Map<String, dynamic>.from(run['metrics_summary'] as Map)
        : (run['metrics'] is Map
            ? Map<String, dynamic>.from(run['metrics'] as Map)
            : <String, dynamic>{});
    final rows = _resultRows(run: run, results: results, apis: apis);
    final status = '${run['status'] ?? ''}';
    final grafana = '${run['grafana_url'] ?? ''}';
    final embed = '${run['grafana_embed_url'] ?? ''}';
    final isLive = status == 'running' || status == 'pending';

    var totalPass = 0;
    var totalFail = 0;
    for (final a in rows) {
      totalPass += _intFrom(
        a['pass'] ?? a['pass_count'] ?? a['passed_count'] ?? a['ok'],
        0,
      );
      totalFail += _intFrom(
        a['fail'] ?? a['fail_count'] ?? a['failed_count'] ?? a['ko'],
        0,
      );
      if (a['checks_passed'] == true || a['passed'] == true) {
        if (_intFrom(a['pass'] ?? a['pass_count'] ?? a['passed_count'], 0) == 0 &&
            _intFrom(a['fail'] ?? a['fail_count'] ?? a['failed_count'], 0) == 0) {
          totalPass += 1;
        }
      }
      if (a['checks_passed'] == false || a['passed'] == false) {
        if (_intFrom(a['pass'] ?? a['pass_count'] ?? a['passed_count'], 0) == 0 &&
            _intFrom(a['fail'] ?? a['fail_count'] ?? a['failed_count'], 0) == 0) {
          totalFail += 1;
        }
      }
    }
    final apiCount = _intFrom(run['api_count'], rows.isNotEmpty ? rows.length : 0);
    final apiPass = _intFrom(run['api_pass_count'], totalPass);
    final apiFail = _intFrom(run['api_fail_count'], totalFail);
    final failPct = apiCount == 0 ? 0 : ((100 * apiFail) / apiCount).round();
    final err = '${run['error'] ?? ''}'.trim();
    final target = '${run['target_url'] ?? run['base_url'] ?? ''}'.trim();

    return ListView(
      padding: const EdgeInsets.only(top: 4),
      children: [
        if (err.isNotEmpty) ...[
          Material(
            color: Theme.of(context).colorScheme.errorContainer.withValues(alpha: 0.35),
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.error_outline, size: 18, color: Theme.of(context).colorScheme.error),
                  const SizedBox(width: 8),
                  Expanded(
                    child: SelectableText(
                      _prettyError(err),
                      maxLines: 3,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Theme.of(context).colorScheme.error,
                            height: 1.3,
                          ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
        ],
        GlassCard(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                spacing: 10,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  _metricTile(context, _isPlaywrightRun(run) ? 'Steps' : 'APIs', '$apiCount'),
                  _metricTile(context, 'Pass', '$apiPass', ok: true),
                  _metricTile(context, 'Fail', '$apiFail', bad: apiFail > 0),
                  _metricTile(context, 'Fail%', '$failPct%', bad: failPct > 0),
                  if (grafana.isNotEmpty)
                    OutlinedButton.icon(
                      onPressed: () => launchUrl(Uri.parse(grafana)),
                      icon: const Icon(Icons.open_in_new, size: 14),
                      label: const Text('Grafana'),
                    ),
                  if (embed.isNotEmpty)
                    OutlinedButton.icon(
                      onPressed: () => launchUrl(Uri.parse(embed)),
                      icon: const Icon(Icons.fullscreen, size: 14),
                      label: const Text('Embed'),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: [
                  _kvChip('profile', '${run['run_profile'] ?? params['profile'] ?? '—'}'),
                  _kvChip('dataset', _payloadSetVersionLabel(run)),
                  _kvChip('VUs', '${params['vus'] ?? run['vus'] ?? '—'}'),
                  _kvChip(
                    'calls',
                    '${params['iterations'] ?? params['calls'] ?? run['iterations'] ?? '—'}',
                  ),
                  _kvChip('duration', '${params['duration'] ?? run['duration'] ?? '—'}'),
                  _kvChip('service', '${run['service'] ?? '—'}'),
                  _kvChip('env', '${run['environment'] ?? '—'}'),
                  if (target.isNotEmpty) _kvChip('target', target),
                  _kvChip('started', _shortTs(run['started_at'])),
                  _kvChip('finished', _shortTs(run['finished_at'])),
                ],
              ),
              if (metrics.isNotEmpty)
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  dense: true,
                  title: Text(
                    'Raw metrics (${metrics.length})',
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                  children: [
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: [
                          for (final e in metrics.entries)
                            Chip(
                              visualDensity: VisualDensity.compact,
                              label: Text('${e.key}: ${e.value}'),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
            ],
          ),
        ),
        Builder(
          builder: (context) {
            final runId = '${run['id'] ?? run['run_id'] ?? ''}'.trim();
            final reportUrl = '${run['ui_report_html_url'] ?? ''}'.trim();
            final hasUi = run['ui_report'] != null || reportUrl.isNotEmpty;
            if (!hasUi || runId.isEmpty) return const SizedBox.shrink();
            final href = reportUrl.isNotEmpty
                ? absUrl(reportUrl)
                : absUrl('/api/runs/$runId/artifacts/ui-report.html');
            return Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.tonalIcon(
                  onPressed: () => launchUrl(Uri.parse(href)),
                  icon: const Icon(Icons.language, size: 18),
                  label: const Text('Open UI report'),
                ),
              ),
            );
          },
        ),
        if (baseline != null && baseline!.isNotEmpty) ...[
          const SizedBox(height: 8),
          _BaselineCard(baseline: baseline!),
        ],
        const SizedBox(height: 4),
        Text(
          'Tip: Inspector → Test APIs · Artifacts → screenshots / PDF / HTML reports for UI runs.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          dense: true,
          title: const Text('Raw JSON'),
          children: [
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: SelectableText(
                const JsonEncoder.withIndent('  ').convert({
                  'id': run['id'],
                  'status': run['status'],
                  'passed': run['passed'],
                  'api_count': run['api_count'],
                  'api_pass_count': run['api_pass_count'],
                  'api_fail_count': run['api_fail_count'],
                  'params': params,
                  'summary': run['summary'],
                  'results': results,
                  'error': run['error'],
                  'target_url': run['target_url'],
                }),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _kvChip(String k, String v) => Chip(
        visualDensity: VisualDensity.compact,
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        label: Text('$k: $v', style: const TextStyle(fontSize: 12)),
        padding: EdgeInsets.zero,
        labelPadding: const EdgeInsets.symmetric(horizontal: 8),
      );

  Widget _metricTile(
    BuildContext context,
    String label,
    String value, {
    bool ok = false,
    bool bad = false,
  }) {
    final color = ok
        ? Colors.green
        : (bad ? Theme.of(context).colorScheme.error : AppColors.primary);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          Text(
            value,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
      ),
    );
  }
}
