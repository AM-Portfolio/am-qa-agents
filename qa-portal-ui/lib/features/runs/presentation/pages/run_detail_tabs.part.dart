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
          ? const Center(child: Text('None yet'))
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

class _ApisTab extends StatelessWidget {
  const _ApisTab({required this.apis});

  final List<Map<String, dynamic>> apis;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(8),
      child: apis.isEmpty
          ? const Center(child: Text('No step/API rows'))
          : SingleChildScrollView(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: DataTable(
                  headingRowHeight: 36,
                  dataRowMinHeight: 36,
                  dataRowMaxHeight: 48,
                  columns: const [
                    DataColumn(label: Text('Step/API')),
                    DataColumn(label: Text('HTTP'), numeric: true),
                    DataColumn(label: Text('Calls'), numeric: true),
                    DataColumn(label: Text('Pass'), numeric: true),
                    DataColumn(label: Text('Fail'), numeric: true),
                    DataColumn(label: Text('Avg ms'), numeric: true),
                    DataColumn(label: Text('p90 ms'), numeric: true),
                    DataColumn(label: Text('Result')),
                  ],
                  rows: [
                    for (final a in apis)
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
                            Text('${a['calls'] ?? a['count'] ?? a['request_count'] ?? a['iterations'] ?? '—'}'),
                          ),
                          DataCell(
                            Text('${a['pass'] ?? a['pass_count'] ?? a['passed_count'] ?? a['ok'] ?? '—'}'),
                          ),
                          DataCell(
                            Text('${a['fail'] ?? a['fail_count'] ?? a['failed_count'] ?? a['ko'] ?? '—'}'),
                          ),
                          DataCell(
                            Text(
                              _fmtMs(a['avg_ms'] ?? a['avg'] ?? a['latency_avg'] ?? a['duration_ms']),
                            ),
                          ),
                          DataCell(
                            Text(
                              _fmtMs(a['p90_ms'] ?? a['p90'] ?? a['latency_p90']),
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
            ),
    );
  }
}
