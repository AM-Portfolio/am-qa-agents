import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../cubit/specs_cubit.dart';
import 'datasets_values_panel.dart';

/// Dense APIs table: params/headers/body previews, expand, curl, quick test.
class DatasetsApisTable extends StatefulWidget {
  const DatasetsApisTable({
    super.key,
    required this.state,
    required this.cubit,
    required this.rows,
    required this.onEdit,
  });

  final SpecsState state;
  final SpecsCubit cubit;
  final List<Map<String, dynamic>> rows;
  final Future<void> Function(BuildContext context, Map<String, dynamic> row)
      onEdit;

  @override
  State<DatasetsApisTable> createState() => _DatasetsApisTableState();
}

class _DatasetsApisTableState extends State<DatasetsApisTable>
    with SingleTickerProviderStateMixin {
  String _filter = '';
  String? _expandedApiId;
  String? _testingApiId;
  String? _lastTestNote;
  bool _prettyJson = true;
  late final TabController _payloadTabs;

  @override
  void initState() {
    super.initState();
    _payloadTabs = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _payloadTabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final cubit = widget.cubit;
    final selected = state.selectedPayloadApiIds;
    final busy = state.payloadListLoading ||
        state.payloadRowsLoading ||
        state.loading;
    final q = _filter.trim().toLowerCase();
    final rows = q.isEmpty
        ? widget.rows
        : widget.rows.where((r) {
            final method = '${r['method'] ?? ''}'.toLowerCase();
            final path = '${r['path'] ?? ''}'.toLowerCase();
            final id = '${r['api_id'] ?? ''}'.toLowerCase();
            final name = '${r['name'] ?? ''}'.toLowerCase();
            return method.contains(q) ||
                path.contains(q) ||
                id.contains(q) ||
                name.contains(q);
          }).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          height: 36,
          child: TextField(
            decoration: InputDecoration(
              isDense: true,
              hintText: 'Filter method / path / api_id…',
              prefixIcon: const Icon(Icons.search, size: 18),
              border: const OutlineInputBorder(),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
              suffixIcon: _filter.isEmpty
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.clear, size: 16),
                      onPressed: () => setState(() => _filter = ''),
                    ),
            ),
            style: const TextStyle(fontSize: 12),
            onChanged: (v) => setState(() => _filter = v),
          ),
        ),
        const SizedBox(height: 6),
        Expanded(
          child: SingleChildScrollView(
            scrollDirection: Axis.vertical,
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  minWidth: MediaQuery.sizeOf(context).width - 48,
                ),
                child: DataTable(
                  headingRowHeight: 30,
                  dataRowMinHeight: 40,
                  dataRowMaxHeight: 56,
                  columnSpacing: 10,
                  horizontalMargin: 4,
                  showCheckboxColumn: false,
                  columns: const [
                    DataColumn(label: Text('')),
                    DataColumn(label: Text('')),
                    DataColumn(label: Text('Method')),
                    DataColumn(label: Text('Path')),
                    DataColumn(label: Text('Name')),
                    DataColumn(label: Text('Run')),
                    DataColumn(label: Text('Curl')),
                    DataColumn(label: Text('Params')),
                    DataColumn(label: Text('Headers')),
                    DataColumn(label: Text('Body')),
                    DataColumn(label: Text('Edit')),
                  ],
                  rows: [
                    for (final r in rows)
                      DataRow(
                        selected: selected.contains('${r['api_id'] ?? ''}'),
                        cells: [
                          DataCell(
                            IconButton(
                              tooltip: 'Expand payload',
                              icon: Icon(
                                _expandedApiId == '${r['api_id'] ?? ''}'
                                    ? Icons.expand_less
                                    : Icons.expand_more,
                                size: 18,
                              ),
                              onPressed: () {
                                final id = '${r['api_id'] ?? ''}';
                                setState(() {
                                  _expandedApiId =
                                      _expandedApiId == id ? null : id;
                                  if (_expandedApiId != null) {
                                    _payloadTabs.index = 0;
                                  }
                                });
                              },
                            ),
                          ),
                          DataCell(
                            Checkbox(
                              value:
                                  selected.contains('${r['api_id'] ?? ''}'),
                              onChanged: '${r['api_id'] ?? ''}'.isEmpty
                                  ? null
                                  : (v) => cubit.togglePayloadApiSelection(
                                        '${r['api_id']}',
                                        selected: v == true,
                                      ),
                            ),
                          ),
                          DataCell(
                            Text(
                              '${r['method'] ?? 'GET'}'.toUpperCase(),
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                                color: _methodColor('${r['method'] ?? ''}'),
                              ),
                            ),
                          ),
                          DataCell(
                            SizedBox(
                              width: 160,
                              child: Text(
                                '${r['path'] ?? ''}',
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 11,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ),
                          DataCell(
                            SizedBox(
                              width: 100,
                              child: Text(
                                '${r['name'] ?? r['api_id'] ?? ''}',
                                style: const TextStyle(fontSize: 11),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ),
                          DataCell(
                            FilledButton.tonal(
                              style: FilledButton.styleFrom(
                                visualDensity: VisualDensity.compact,
                                padding:
                                    const EdgeInsets.symmetric(horizontal: 10),
                                minimumSize: const Size(0, 30),
                              ),
                              onPressed: busy
                                  ? null
                                  : () => _quickTest(context, r),
                              child: _testingApiId == '${r['api_id'] ?? ''}'
                                  ? const SizedBox(
                                      width: 14,
                                      height: 14,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                      ),
                                    )
                                  : const Text('Run'),
                            ),
                          ),
                          DataCell(
                            IconButton(
                              tooltip: 'Copy curl',
                              icon: const Icon(Icons.copy_all, size: 18),
                              onPressed: () async {
                                final curl = cubit.curlForPayloadRow(r);
                                await Clipboard.setData(
                                  ClipboardData(text: curl),
                                );
                                if (!context.mounted) return;
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('curl copied'),
                                    behavior: SnackBarBehavior.floating,
                                  ),
                                );
                              },
                            ),
                          ),
                          DataCell(
                            SizedBox(
                              width: 120,
                              child: Text(
                                _paramsPreview(r),
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 10,
                                ),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ),
                          DataCell(
                            SizedBox(
                              width: 100,
                              child: Text(
                                _headersPreview(r),
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 10,
                                ),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ),
                          DataCell(
                            InkWell(
                              onTap: () {
                                final id = '${r['api_id'] ?? ''}';
                                setState(() {
                                  _expandedApiId =
                                      _expandedApiId == id ? null : id;
                                  if (_expandedApiId != null) {
                                    _payloadTabs.index = 0;
                                  }
                                });
                              },
                              child: SizedBox(
                                width: 120,
                                child: Text(
                                  _bodyPreview(r),
                                  style: const TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 10,
                                  ),
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ),
                          ),
                          DataCell(
                            FilledButton.tonal(
                              style: FilledButton.styleFrom(
                                visualDensity: VisualDensity.compact,
                                padding:
                                    const EdgeInsets.symmetric(horizontal: 8),
                                minimumSize: const Size(0, 28),
                              ),
                              onPressed:
                                  busy ? null : () => widget.onEdit(context, r),
                              child: const Text('Edit'),
                            ),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
        if (_expandedApiId != null) _expandedPanel(rows, _expandedApiId!),
        if (_lastTestNote != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(
              _lastTestNote!,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        if (rows.isEmpty)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text(
              'No APIs match “$_filter”.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
      ],
    );
  }

  Future<void> _quickTest(
    BuildContext context,
    Map<String, dynamic> row,
  ) async {
    final id = '${row['api_id'] ?? ''}';
    setState(() {
      _testingApiId = id;
      _lastTestNote = null;
    });
    try {
      final out = await widget.cubit.quickTestPayloadRow(row);
      if (!mounted) return;
      setState(() {
        _testingApiId = null;
        _lastTestNote =
            'Run $id → ${out.status ?? '?'} (${out.ms ?? 0}ms) ${out.body}';
        _expandedApiId = id;
        _payloadTabs.index = 1;
      });
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Test ${out.status ?? '?'} · ${out.ms ?? 0}ms'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _testingApiId = null;
        _lastTestNote = 'Test failed: $e';
      });
    }
  }

  Widget _expandedPanel(List<Map<String, dynamic>> rows, String apiId) {
    Map<String, dynamic>? row;
    for (final r in rows) {
      if ('${r['api_id'] ?? ''}' == apiId) {
        row = r;
        break;
      }
    }
    if (row == null) return const SizedBox.shrink();
    final req = DatasetsValuesPanel.requestOf(row);
    final resp = row['response'] ?? {};
    final reqText = _formatJson(req, pretty: _prettyJson);
    final respText = _formatJson(resp, pretty: _prettyJson);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Divider(height: 12),
        Row(
          children: [
            Expanded(
              child: Text(
                'Full payload · $apiId',
                style: Theme.of(context).textTheme.labelLarge,
              ),
            ),
            FilterChip(
              label: const Text('Pretty'),
              selected: _prettyJson,
              visualDensity: VisualDensity.compact,
              onSelected: (v) => setState(() => _prettyJson = v),
            ),
          ],
        ),
        const SizedBox(height: 4),
        TabBar(
          controller: _payloadTabs,
          isScrollable: true,
          tabs: const [
            Tab(text: 'Request'),
            Tab(text: 'Response'),
          ],
        ),
        SizedBox(
          height: 240,
          child: TabBarView(
            controller: _payloadTabs,
            children: [
              SingleChildScrollView(
                padding: const EdgeInsets.only(top: 8),
                child: SelectableText(
                  reqText,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                ),
              ),
              SingleChildScrollView(
                padding: const EdgeInsets.only(top: 8),
                child: SelectableText(
                  respText,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  static String _formatJson(Object? value, {required bool pretty}) {
    try {
      if (pretty) {
        return const JsonEncoder.withIndent('  ').convert(value);
      }
      return jsonEncode(value);
    } catch (_) {
      return '$value';
    }
  }

  static Color _methodColor(String method) {
    switch (method.toUpperCase()) {
      case 'GET':
        return const Color(0xFF2563EB);
      case 'POST':
        return const Color(0xFF16A34A);
      case 'PUT':
        return const Color(0xFFD97706);
      case 'PATCH':
        return const Color(0xFFCA8A04);
      case 'DELETE':
        return const Color(0xFFDC2626);
      default:
        return const Color(0xFF64748B);
    }
  }

  static String _previewMap(dynamic raw, {int maxLen = 48}) {
    if (raw is! Map || raw.isEmpty) return '—';
    final parts = <String>[];
    for (final e in raw.entries) {
      parts.add('${e.key}=${e.value}');
      if (parts.join(', ').length > maxLen) break;
    }
    var s = parts.join(', ');
    if (s.length > maxLen) s = '${s.substring(0, maxLen - 1)}…';
    return s.isEmpty ? '—' : s;
  }

  static String _paramsPreview(Map<String, dynamic> r) {
    final req = DatasetsValuesPanel.requestOf(r);
    final path = _previewMap(req['path_params'], maxLen: 24);
    final query = _previewMap(req['query'] ?? req['query_params'], maxLen: 24);
    if (path == '—' && query == '—') return '—';
    if (path == '—') return query;
    if (query == '—') return path;
    return '$path · $query';
  }

  static String _headersPreview(Map<String, dynamic> r) {
    return _previewMap(DatasetsValuesPanel.requestOf(r)['headers']);
  }

  static String _bodyPreview(Map<String, dynamic> r) {
    final req = DatasetsValuesPanel.requestOf(r);
    final body = req['body'];
    if (body == null) return '—';
    String s;
    try {
      s = body is String ? body : jsonEncode(body);
    } catch (_) {
      s = '$body';
    }
    s = s.replaceAll(RegExp(r'\s+'), ' ').trim();
    if (s.isEmpty) return '—';
    return s.length > 64 ? '${s.substring(0, 61)}…' : s;
  }
}
