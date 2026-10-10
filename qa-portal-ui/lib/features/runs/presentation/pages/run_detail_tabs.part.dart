part of 'run_detail_page.dart';

class _ArtifactsTab extends StatelessWidget {
  const _ArtifactsTab({required this.artifacts, required this.absUrl});

  final List<Map<String, dynamic>> artifacts;
  final String Function(String) absUrl;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: EdgeInsets.zero,
      child: artifacts.isEmpty
          ? Center(
              child: Text(
                'No artifacts yet.\nUI runs attach screenshots, PDF, and HTML reports here when finished.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            )
          : ListView.separated(
              itemCount: artifacts.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, i) {
                final a = artifacts[i];
                final name = '${a['name'] ?? a['path'] ?? ''}';
                final url = '${a['url'] ?? ''}';
                final minio = '${a['minio_url'] ?? ''}';
                final kind = '${a['kind'] ?? a['type'] ?? ''}'.toLowerCase();
                return ListTile(
                  leading: Icon(
                    kind.contains('html') || kind.contains('report')
                        ? Icons.language
                        : (kind.contains('pdf')
                            ? Icons.picture_as_pdf
                            : (kind.contains('json')
                                ? Icons.data_object
                                : (kind.contains('image')
                                    ? Icons.image
                                    : Icons.attachment))),
                  ),
                  title: Text(name),
                  subtitle: Text('${a['kind'] ?? ''} · ${a['size'] ?? ''} bytes'),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (url.isNotEmpty)
                        IconButton(
                          icon: const Icon(Icons.download),
                          onPressed: () => launchUrl(Uri.parse(absUrl(url))),
                        ),
                      if (minio.isNotEmpty)
                        IconButton(
                          icon: const Icon(Icons.cloud),
                          onPressed: () => launchUrl(Uri.parse(minio)),
                        ),
                    ],
                  ),
                );
              },
            ),
    );
  }
}

class _ApisTab extends StatefulWidget {
  const _ApisTab({
    required this.run,
    required this.apis,
    required this.selected,
    required this.showTry,
    required this.onSelect,
    required this.onShowTry,
  });

  final Map<String, dynamic> run;
  final List<Map<String, dynamic>> apis;
  final Map<String, dynamic>? selected;
  final bool showTry;
  final ValueChanged<Map<String, dynamic>?> onSelect;
  final ValueChanged<bool> onShowTry;

  @override
  State<_ApisTab> createState() => _ApisTabState();
}

class _ApisTabState extends State<_ApisTab> {
  static const _listDefault = 280.0;
  static const _listMin = 160.0;

  bool _listCollapsed = false;
  double _listWidth = _listDefault;

  Map<String, dynamic> get run => widget.run;
  List<Map<String, dynamic>> get apis => widget.apis;
  Map<String, dynamic>? get selected => widget.selected;
  bool get showTry => widget.showTry;
  ValueChanged<Map<String, dynamic>?> get onSelect => widget.onSelect;
  ValueChanged<bool> get onShowTry => widget.onShowTry;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 960;

    return GlassCard(
      padding: const EdgeInsets.all(8),
      child: wide
          ? LayoutBuilder(
              builder: (context, constraints) {
                final maxList = (constraints.maxWidth * 0.55)
                    .clamp(_listMin, constraints.maxWidth - 280);
                final listW = _listWidth.clamp(_listMin, maxList);
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (_listCollapsed)
                      _collapsedListRail(context)
                    else ...[
                      SizedBox(
                        width: listW,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    'Step/API',
                                    style: Theme.of(context)
                                        .textTheme
                                        .labelLarge
                                        ?.copyWith(fontWeight: FontWeight.w700),
                                  ),
                                ),
                                IconButton(
                                  tooltip: 'Hide Step/API list',
                                  visualDensity: VisualDensity.compact,
                                  onPressed: () =>
                                      setState(() => _listCollapsed = true),
                                  icon: const Icon(Icons.chevron_left, size: 20),
                                ),
                              ],
                            ),
                            const SizedBox(height: 4),
                            Expanded(child: _table(context)),
                          ],
                        ),
                      ),
                      MouseRegion(
                        cursor: SystemMouseCursors.resizeColumn,
                        child: GestureDetector(
                          behavior: HitTestBehavior.opaque,
                          onHorizontalDragUpdate: (d) {
                            setState(() {
                              _listWidth = (_listWidth + d.delta.dx)
                                  .clamp(_listMin, maxList);
                            });
                          },
                          onDoubleTap: () =>
                              setState(() => _listWidth = _listDefault),
                          child: SizedBox(
                            width: 10,
                            child: Center(
                              child: Container(
                                width: 3,
                                height: 48,
                                decoration: BoxDecoration(
                                  color: Theme.of(context)
                                      .dividerColor
                                      .withValues(alpha: 0.9),
                                  borderRadius: BorderRadius.circular(2),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                    Expanded(
                      child: selected == null
                          ? Center(
                              child: Text(
                                'Select a Step/API to inspect',
                                style: Theme.of(context).textTheme.bodyMedium,
                              ),
                            )
                          : _detail(context, selected!),
                    ),
                  ],
                );
              },
            )
          : Column(
              children: [
                if (!_listCollapsed) ...[
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Step/API',
                          style: Theme.of(context)
                              .textTheme
                              .labelLarge
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                      ),
                      if (selected != null)
                        IconButton(
                          tooltip: 'Hide Step/API list',
                          visualDensity: VisualDensity.compact,
                          onPressed: () =>
                              setState(() => _listCollapsed = true),
                          icon: const Icon(Icons.expand_less, size: 20),
                        ),
                    ],
                  ),
                  Expanded(child: _table(context)),
                ] else
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      onPressed: () => setState(() => _listCollapsed = false),
                      icon: const Icon(Icons.expand_more, size: 18),
                      label: const Text('Show Step/API'),
                    ),
                  ),
                if (selected != null) ...[
                  const Divider(height: 12),
                  Expanded(flex: 2, child: _detail(context, selected!)),
                ],
              ],
            ),
    );
  }

  Widget _collapsedListRail(BuildContext context) {
    return Tooltip(
      message: 'Show Step/API list',
      child: InkWell(
        onTap: () => setState(() => _listCollapsed = false),
        child: SizedBox(
          width: 36,
          child: Column(
            children: [
              const SizedBox(height: 4),
              Icon(
                Icons.chevron_right,
                size: 20,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(height: 8),
              Expanded(
                child: RotatedBox(
                  quarterTurns: 3,
                  child: Center(
                    child: Text(
                      'Step/API',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _table(BuildContext context) {
    if (apis.isEmpty) {
      return const Center(child: Text('No step/API rows'));
    }
    final selId = selected == null ? null : _apiRowLabel(selected!);
    return SingleChildScrollView(
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTable(
          headingRowHeight: 36,
          dataRowMinHeight: 36,
          dataRowMaxHeight: 48,
          showCheckboxColumn: false,
          columns: const [
            DataColumn(label: Text('Step/API')),
            DataColumn(label: Text('HTTP'), numeric: true),
            DataColumn(label: Text('Calls'), numeric: true),
            DataColumn(label: Text('Pass'), numeric: true),
            DataColumn(label: Text('Fail'), numeric: true),
            DataColumn(label: Text('Avg ms'), numeric: true),
            DataColumn(label: Text('Result')),
          ],
          rows: [
            for (final a in apis)
              DataRow(
                selected: selId != null && _apiRowLabel(a) == selId,
                onSelectChanged: (_) => onSelect(a),
                cells: [
                  DataCell(Text(_apiRowLabel(a))),
                  DataCell(
                    Text(_httpStatusOf(a)),
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
                      _fmtMs(
                        a['avg_ms'] ?? a['avg'] ?? a['latency_avg'] ?? a['duration_ms'],
                      ),
                    ),
                  ),
                  DataCell(
                    Text(
                      _apiRowResultLabel(a),
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        color: _apiRowFailed(a)
                            ? Theme.of(context).colorScheme.error
                            : (a['checks_passed'] == true || a['passed'] == true
                                ? Colors.green
                                : null),
                      ),
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  Widget _detail(BuildContext context, Map<String, dynamic> row) {
    if (showTry) {
      return RunApiTryPanel(
        key: ValueKey(_apiRowLabel(row)),
        run: run,
        row: row,
        onClose: () => onShowTry(false),
      );
    }

    final err = '${row['error'] ?? row['error_message'] ?? row['message'] ?? ''}'.trim();
    final req = row['request'] ?? row['request_body'] ?? row['req'];
    final res = row['response'] ?? row['response_body'] ?? row['body'];
    final pretty = const JsonEncoder.withIndent('  ');

    String asJson(Object? v) {
      if (v == null) return '—';
      if (v is String) {
        try {
          return pretty.convert(jsonDecode(v));
        } catch (_) {
          return v;
        }
      }
      try {
        return pretty.convert(v);
      } catch (_) {
        return '$v';
      }
    }

    return ListView(
      padding: const EdgeInsets.all(4),
      children: [
        Text(
          _apiRowLabel(row),
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 4),
        Wrap(
          spacing: 8,
          runSpacing: 4,
          children: [
            Chip(
              visualDensity: VisualDensity.compact,
              label: Text('HTTP ${_httpStatusOf(row)}'),
            ),
            Chip(
              visualDensity: VisualDensity.compact,
              label: Text(_apiRowResultLabel(row)),
            ),
            if ('${row['method'] ?? ''}'.isNotEmpty)
              Chip(
                visualDensity: VisualDensity.compact,
                label: Text('${row['method']}'),
              ),
          ],
        ),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerLeft,
          child: FilledButton.tonalIcon(
            onPressed: () => onShowTry(true),
            icon: const Icon(Icons.science, size: 18),
            label: const Text('Open Test'),
          ),
        ),
        if (err.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text('Error', style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 4),
          SelectableText(
            _prettyError(err),
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  fontFamily: 'Consolas',
                  color: Theme.of(context).colorScheme.error,
                ),
          ),
        ],
        const SizedBox(height: 12),
        Text('Request', style: Theme.of(context).textTheme.labelMedium),
        const SizedBox(height: 4),
        SelectableText(
          asJson(req),
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontFamily: 'Consolas',
              ),
        ),
        const SizedBox(height: 12),
        Text('Response', style: Theme.of(context).textTheme.labelMedium),
        const SizedBox(height: 4),
        SelectableText(
          asJson(res),
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontFamily: 'Consolas',
              ),
        ),
      ],
    );
  }
}
