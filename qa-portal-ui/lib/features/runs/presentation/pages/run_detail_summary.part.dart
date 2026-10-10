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

    var totalCalls = 0;
    var totalPass = 0;
    var totalFail = 0;
    for (final a in rows) {
      totalCalls += _intFrom(a['calls'] ?? a['count'] ?? a['iterations'], 0);
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
    // Prefer run-level aggregates when present (list/detail API).
    final apiCount = _intFrom(run['api_count'], rows.isNotEmpty ? rows.length : totalCalls);
    final apiPass = _intFrom(run['api_pass_count'], totalPass);
    final apiFail = _intFrom(run['api_fail_count'], totalFail);
    final failPct = apiCount == 0 ? 0 : ((100 * apiFail) / apiCount).round();
    final err = '${run['error'] ?? ''}'.trim();

    return ListView(
      padding: const EdgeInsets.only(top: 8),
      children: [
        if (err.isNotEmpty) ...[
          GlassCard(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Icon(Icons.error_outline, color: Theme.of(context).colorScheme.error),
                    const SizedBox(width: 8),
                    Text(
                      'Error',
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            color: Theme.of(context).colorScheme.error,
                          ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                SelectableText(
                  _prettyError(err),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontFamily: 'Consolas',
                        height: 1.35,
                      ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
        ],
        GlassCard(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Parameters', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _kvChip('profile', '${run['run_profile'] ?? params['profile'] ?? '—'}'),
                  _kvChip('VUs', '${params['vus'] ?? run['vus'] ?? '—'}'),
                  _kvChip(
                    'calls',
                    '${params['iterations'] ?? params['calls'] ?? run['iterations'] ?? '—'}',
                  ),
                  _kvChip('duration', '${params['duration'] ?? run['duration'] ?? '—'}'),
                  _kvChip('service', '${run['service'] ?? '—'}'),
                  _kvChip('env', '${run['environment'] ?? '—'}'),
                  _kvChip('started', '${run['started_at'] ?? '—'}'),
                  _kvChip('finished', '${run['finished_at'] ?? '—'}'),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        GlassCard(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Outcome',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 12,
                runSpacing: 8,
                children: [
                  _metricTile(
                    context,
                    _isPlaywrightRun(run) ? 'Steps' : 'APIs',
                    '$apiCount',
                  ),
                  _metricTile(context, 'Pass', '$apiPass', ok: true),
                  _metricTile(
                    context,
                    'Fail',
                    '$apiFail',
                    bad: apiFail > 0,
                  ),
                  _metricTile(
                    context,
                    'Fail%',
                    '$failPct%',
                    bad: failPct > 0,
                  ),
                ],
              ),
              if (metrics.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(
                  'Metrics (RPS · latency · data)',
                  style: Theme.of(context).textTheme.labelMedium,
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final e in metrics.entries.take(12))
                      Chip(
                        visualDensity: VisualDensity.compact,
                        label: Text('${e.key}: ${e.value}'),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 8),
        GlassCard(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Grafana', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 6),
              if (isLive)
                Text(
                  'Grafana unlocks when the run finishes.',
                  style: Theme.of(context).textTheme.bodySmall,
                )
              else if (grafana.isEmpty && embed.isEmpty)
                Text(
                  'Grafana URL unavailable.',
                  style: Theme.of(context).textTheme.bodySmall,
                )
              else ...[
                if (metrics.isEmpty)
                  Text(
                    'No chart data for this run.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 8,
                  children: [
                    if (grafana.isNotEmpty)
                      OutlinedButton.icon(
                        onPressed: () => launchUrl(Uri.parse(grafana)),
                        icon: const Icon(Icons.open_in_new, size: 16),
                        label: const Text('Open Grafana'),
                      ),
                    if (embed.isNotEmpty)
                      OutlinedButton.icon(
                        onPressed: () => launchUrl(Uri.parse(embed)),
                        icon: const Icon(Icons.fullscreen, size: 16),
                        label: const Text('Open embed / kiosk'),
                      ),
                  ],
                ),
              ],
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
              child: GlassCard(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text('Playwright report', style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 8),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: FilledButton.tonalIcon(
                        onPressed: () => launchUrl(Uri.parse(href)),
                        icon: const Icon(Icons.language, size: 18),
                        label: const Text('Open UI report'),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
        if (baseline != null && baseline!.isNotEmpty) ...[
          const SizedBox(height: 8),
          _BaselineCard(baseline: baseline!),
        ],
        const SizedBox(height: 8),
        GlassCard(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Results table',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              if (rows.isEmpty)
                Text(
                  isLive
                      ? (_isPlaywrightRun(run)
                          ? 'Results stream when UI steps finish…'
                          : 'Results stream when APIs finish…')
                      : (_isPlaywrightRun(run)
                          ? 'No UI steps for this run.'
                          : 'No API result rows for this run.'),
                  style: Theme.of(context).textTheme.bodySmall,
                )
              else
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: DataTable(
                    headingRowHeight: 36,
                    dataRowMinHeight: 36,
                    dataRowMaxHeight: 48,
                    columns: [
                      DataColumn(
                        label: Text(_isPlaywrightRun(run) ? 'Step' : 'API'),
                      ),
                      const DataColumn(label: Text('HTTP'), numeric: true),
                      const DataColumn(label: Text('Calls'), numeric: true),
                      const DataColumn(label: Text('Pass'), numeric: true),
                      const DataColumn(label: Text('Fail'), numeric: true),
                      const DataColumn(label: Text('Fail%'), numeric: true),
                      const DataColumn(label: Text('Avg ms'), numeric: true),
                      const DataColumn(label: Text('p90 ms'), numeric: true),
                      DataColumn(label: Text('Result')),
                    ],
                    rows: [
                      for (final a in rows)
                        DataRow(
                          cells: [
                            DataCell(
                              Text(
                                '${a['api_id'] ?? a['id'] ?? a['name'] ?? a['path'] ?? ''}',
                              ),
                            ),
                            DataCell(
                              Text(
                                '${a['http_status'] ?? a['status_code'] ?? a['status'] ?? '—'}',
                              ),
                            ),
                            DataCell(
                              Text(
                                '${a['calls'] ?? a['count'] ?? a['request_count'] ?? a['iterations'] ?? '—'}',
                              ),
                            ),
                            DataCell(
                              Text(
                                '${a['pass'] ?? a['pass_count'] ?? a['passed_count'] ?? a['ok'] ?? '—'}',
                              ),
                            ),
                            DataCell(
                              Text(
                                '${a['fail'] ?? a['fail_count'] ?? a['failed_count'] ?? a['ko'] ?? '—'}',
                              ),
                            ),
                            DataCell(
                              Text(
                                '${a['fail_pct'] ?? a['fail_rate'] ?? '—'}',
                              ),
                            ),
                            DataCell(
                              Text(
                                _fmtMs(
                                  a['avg_ms'] ?? a['avg'] ?? a['latency_avg'] ?? a['duration_ms'],
                                ),
                              ),
                            ),
                            DataCell(
                              Text(
                                _fmtMs(
                                  a['p90_ms'] ?? a['p90'] ?? a['latency_p90'],
                                ),
                              ),
                            ),
                            DataCell(
                              Text(
                                a['checks_passed'] == true || a['passed'] == true
                                    ? 'PASS'
                                    : (a['checks_passed'] == false || a['passed'] == false
                                        ? 'FAIL'
                                        : '${a['result'] ?? a['status'] ?? '—'}'),
                                style: TextStyle(
                                  fontWeight: FontWeight.w700,
                                  color: a['checks_passed'] == true || a['passed'] == true
                                      ? Colors.green
                                      : (a['checks_passed'] == false || a['passed'] == false
                                          ? Theme.of(context).colorScheme.error
                                          : null),
                                ),
                              ),
                            ),
                          ],
                        ),
                    ],
                  ),
                ),
              const SizedBox(height: 8),
              Text(
                'Tip: use Inspector tab for request/response of each call.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        ExpansionTile(
          title: const Text('Raw JSON'),
          children: [
            Padding(
              padding: const EdgeInsets.all(12),
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
        label: Text('$k: $v'),
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
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          Text(
            value,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
      ),
    );
  }
}

