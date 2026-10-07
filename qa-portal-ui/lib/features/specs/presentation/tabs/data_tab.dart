import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/specs_cubit.dart';
import '../widgets/import_pickers.dart';
import '../widgets/qa_json_block.dart';

/// One secret / field value reused across payload-set APIs (Test / MCP / Swagger feed).
class _ValueHit {
  const _ValueHit({
    required this.section,
    required this.key,
    required this.value,
    required this.apis,
  });

  final String section;
  final String key;
  final String value;
  final List<String> apis; // "METHOD path"
}

class SpecsDataTab extends StatelessWidget {
  const SpecsDataTab({required this.state});

  final SpecsState state;

  List<Map<String, dynamic>> _rows() => state.generateResults;

  Map<String, dynamic> _requestOf(Map<String, dynamic> r) {
    if (r['request'] is Map) {
      return Map<String, dynamic>.from(r['request'] as Map);
    }
    return {
      'method': r['method'],
      'path': r['path'],
      'query': r['query'],
      'path_params': r['path_params'],
      'body': r['body'],
      'headers': r['headers'],
    };
  }

  String _apiLabel(Map<String, dynamic> r, Map<String, dynamic> req) {
    final m = '${req['method'] ?? r['method'] ?? 'GET'}'.toUpperCase();
    final p = '${req['path'] ?? r['path'] ?? ''}';
    return '$m $p';
  }

  void _addMapValues({
    required Map<String, _ValueHit> bag,
    required String section,
    required dynamic raw,
    required String apiLabel,
    String keyPrefix = '',
  }) {
    if (raw == null) return;
    if (raw is Map) {
      raw.forEach((k, v) {
        final name = keyPrefix.isEmpty ? '$k' : '$keyPrefix.$k';
        if (v is Map || v is List) {
          _addMapValues(
            bag: bag,
            section: section,
            raw: v,
            apiLabel: apiLabel,
            keyPrefix: name,
          );
          return;
        }
        final s = '$v'.trim();
        if (s.isEmpty || s.contains('{{')) return;
        final id = '$section|$name|$s';
        final prev = bag[id];
        if (prev == null) {
          bag[id] = _ValueHit(
            section: section,
            key: name,
            value: s,
            apis: [apiLabel],
          );
        } else if (!prev.apis.contains(apiLabel)) {
          bag[id] = _ValueHit(
            section: prev.section,
            key: prev.key,
            value: prev.value,
            apis: [...prev.apis, apiLabel],
          );
        }
      });
      return;
    }
    if (raw is List) {
      for (var i = 0; i < raw.length; i++) {
        _addMapValues(
          bag: bag,
          section: section,
          raw: raw[i],
          apiLabel: apiLabel,
          keyPrefix: keyPrefix.isEmpty ? '[$i]' : '$keyPrefix[$i]',
        );
      }
    }
  }

  List<_ValueHit> _collectValues(List<Map<String, dynamic>> rows) {
    final bag = <String, _ValueHit>{};
    final domain = (state.targetUrl ?? '').trim();
    if (domain.isNotEmpty) {
      bag['domain|base_url|$domain'] = _ValueHit(
        section: 'domain',
        key: 'base_url',
        value: domain,
        apis: const ['(workspace target)'],
      );
    }
    for (final r in rows) {
      final req = _requestOf(r);
      final label = _apiLabel(r, req);
      _addMapValues(
        bag: bag,
        section: 'path_params',
        raw: req['path_params'] ?? req['pathParams'],
        apiLabel: label,
      );
      _addMapValues(
        bag: bag,
        section: 'query',
        raw: req['query'] ?? req['query_params'],
        apiLabel: label,
      );
      _addMapValues(
        bag: bag,
        section: 'headers',
        raw: req['headers'],
        apiLabel: label,
      );
      final body = req['body'] ?? r['body'];
      if (body is Map || body is List) {
        _addMapValues(bag: bag, section: 'body', raw: body, apiLabel: label);
      } else if (body is String && body.trim().isNotEmpty) {
        try {
          final decoded = jsonDecode(body);
          _addMapValues(bag: bag, section: 'body', raw: decoded, apiLabel: label);
        } catch (_) {
          final id = 'body|(raw)|$body';
          bag.putIfAbsent(
            id,
            () => _ValueHit(
              section: 'body',
              key: '(raw)',
              value: body.length > 120 ? '${body.substring(0, 117)}…' : body,
              apis: [label],
            ),
          );
        }
      }
    }
    final order = const ['domain', 'path_params', 'query', 'headers', 'body'];
    final list = bag.values.toList()
      ..sort((a, b) {
        final sa = order.indexOf(a.section);
        final sb = order.indexOf(b.section);
        final c = (sa < 0 ? 99 : sa).compareTo(sb < 0 ? 99 : sb);
        if (c != 0) return c;
        final kc = a.key.compareTo(b.key);
        if (kc != 0) return kc;
        return a.value.compareTo(b.value);
      });
    return list;
  }

  Future<void> _confirmDeleteSelected(BuildContext context, SpecsCubit cubit) async {
    final n = state.selectedPayloadApiIds.length;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete selected APIs'),
        content: Text('Remove $n API(s) from payload set v${state.selectedPayloadVersion}?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete')),
        ],
      ),
    );
    if (ok == true) await cubit.deleteSelectedPayloadApis();
  }

  Future<void> _confirmDeleteVersion(BuildContext context, SpecsCubit cubit) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete entire version'),
        content: Text(
          'Permanently delete payload set v${state.selectedPayloadVersion} '
          'for ${state.selectedService}? This cannot be undone.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete version'),
          ),
        ],
      ),
    );
    if (ok == true) await cubit.deleteSelectedPayloadVersion();
  }

  Future<void> _editRow(
    BuildContext context,
    SpecsCubit cubit,
    Map<String, dynamic> row,
  ) async {
    final apiId = '${row['api_id'] ?? ''}';
    if (apiId.isEmpty) return;
    final req = _requestOf(row);
    final resp = row['response'] is Map
        ? Map<String, dynamic>.from(row['response'] as Map)
        : <String, dynamic>{};
    final reqCtrl = TextEditingController(text: const JsonEncoder.withIndent('  ').convert(req));
    final respCtrl = TextEditingController(
      text: resp.isEmpty ? '{}' : const JsonEncoder.withIndent('  ').convert(resp),
    );
    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Edit values · $apiId'),
        content: SizedBox(
          width: 720,
          height: 480,
          child: Column(
            children: [
              Expanded(
                child: TextField(
                  controller: reqCtrl,
                  maxLines: null,
                  expands: true,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                  decoration: const InputDecoration(
                    labelText: 'request values (path_params / query / headers / body)',
                    border: OutlineInputBorder(),
                    alignLabelWithHint: true,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: TextField(
                  controller: respCtrl,
                  maxLines: null,
                  expands: true,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                  decoration: const InputDecoration(
                    labelText: 'response (JSON)',
                    border: OutlineInputBorder(),
                    alignLabelWithHint: true,
                  ),
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
        ],
      ),
    );
    if (saved != true) return;
    try {
      final request = Map<String, dynamic>.from(jsonDecode(reqCtrl.text) as Map);
      final responseRaw = jsonDecode(respCtrl.text);
      final response = responseRaw is Map
          ? Map<String, dynamic>.from(responseRaw)
          : <String, dynamic>{};
      await cubit.editPayloadSetApi(
        apiId: apiId,
        request: request,
        response: response,
        name: '${row['name'] ?? 'working'}',
      );
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Invalid JSON: $e')),
        );
      }
    }
  }

  Widget _sectionHeader(BuildContext context, String section, int count) {
    final labels = {
      'domain': 'Domain / base URL',
      'path_params': 'Path params',
      'query': 'Query params',
      'headers': 'Headers / secrets',
      'body': 'Body fields',
    };
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 12, 4, 4),
      child: Row(
        children: [
          Text(
            labels[section] ?? section,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(width: 8),
          Chip(
            visualDensity: VisualDensity.compact,
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            label: Text('$count', style: Theme.of(context).textTheme.labelSmall),
            padding: EdgeInsets.zero,
            labelPadding: const EdgeInsets.symmetric(horizontal: 6),
          ),
        ],
      ),
    );
  }

  Widget _valueTile(BuildContext context, _ValueHit hit) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 2),
      child: ListTile(
        dense: true,
        title: SelectableText(
          hit.key,
          style: const TextStyle(
            fontFamily: 'monospace',
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 2),
            SelectableText(
              hit.value,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              hit.apis.length == 1
                  ? 'used in ${hit.apis.first}'
                  : 'used in ${hit.apis.length} APIs · ${hit.apis.take(3).join(' · ')}'
                      '${hit.apis.length > 3 ? '…' : ''}',
              style: Theme.of(context).textTheme.labelSmall,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
        trailing: IconButton(
          tooltip: 'Copy value',
          icon: const Icon(Icons.copy, size: 16),
          onPressed: () {
            Clipboard.setData(ClipboardData(text: hit.value));
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Copied ${hit.key}')),
            );
          },
        ),
        onTap: hit.apis.length <= 1
            ? null
            : () {
                showDialog<void>(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    title: Text('${hit.key} = ${hit.value}'),
                    content: SizedBox(
                      width: 480,
                      child: ListView(
                        shrinkWrap: true,
                        children: [
                          for (final a in hit.apis)
                            ListTile(
                              dense: true,
                              title: Text(a, style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
                            ),
                        ],
                      ),
                    ),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
                    ],
                  ),
                );
              },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<SpecsCubit>();
    final summary = state.generateSummary;
    final rows = _rows();
    final values = _collectValues(rows);
    final maxAttempts = 3;
    final selected = state.selectedPayloadApiIds;
    final allIds = [
      for (final r in rows)
        if ('${r['api_id'] ?? ''}'.isNotEmpty) '${r['api_id']}',
    ];

    final bySection = <String, List<_ValueHit>>{};
    for (final v in values) {
      bySection.putIfAbsent(v.section, () => []).add(v);
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 6, 8, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Wrap(
            spacing: 6,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                state.selectedPayloadVersion != null
                    ? 'Secrets & values · data v${state.selectedPayloadVersion}'
                    : 'Secrets & values',
                style: Theme.of(context).textTheme.labelLarge,
              ),
              TextButton.icon(
                onPressed: state.generating || state.selectedService == null
                    ? null
                    : () => pickAndImportPostman(context, cubit, envOnly: false),
                icon: const Icon(Icons.upload_file, size: 16),
                label: const Text('Import'),
              ),
              TextButton.icon(
                onPressed: state.generating || state.selectedService == null
                    ? null
                    : () => pickAndImportPostman(context, cubit, envOnly: true),
                icon: const Icon(Icons.tune, size: 16),
                label: const Text('Env'),
              ),
              TextButton(
                onPressed: state.loading || state.selectedPayloadVersion == null
                    ? null
                    : () => _confirmDeleteVersion(context, cubit),
                child: const Text('Delete version'),
              ),
              if (summary != null)
                Chip(
                  visualDensity: VisualDensity.compact,
                  label: Text(
                    '${values.length} values · ${rows.length} APIs',
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 4),
          Expanded(
            child: rows.isEmpty
                ? Center(
                    child: Text(
                      state.generating
                          ? 'Running data prep…'
                          : state.selectedPayloadVersion == null
                              ? 'Select a data version above, or Generate / Import.'
                              : 'No values in this payload set yet.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  )
                : values.isEmpty
                    ? Center(
                        child: Text(
                          'Payload set has ${rows.length} APIs but no filled path/query/header/body values yet.',
                          style: Theme.of(context).textTheme.bodySmall,
                          textAlign: TextAlign.center,
                        ),
                      )
                    : ListView(
                        children: [
                          for (final section in const [
                            'domain',
                            'path_params',
                            'query',
                            'headers',
                            'body',
                          ])
                            if (bySection[section]?.isNotEmpty == true) ...[
                              _sectionHeader(
                                context,
                                section,
                                bySection[section]!.length,
                              ),
                              for (final hit in bySection[section]!)
                                _valueTile(context, hit),
                            ],
                          const SizedBox(height: 12),
                          ExpansionTile(
                            initiallyExpanded: false,
                            title: Text(
                              'Edit by API (${rows.length})',
                              style: Theme.of(context).textTheme.labelLarge,
                            ),
                            subtitle: Text(
                              'JSON edit / multi-delete for the underlying set rows',
                              style: Theme.of(context).textTheme.labelSmall,
                            ),
                            children: [
                              Padding(
                                padding: const EdgeInsets.symmetric(horizontal: 8),
                                child: Wrap(
                                  spacing: 6,
                                  children: [
                                    TextButton(
                                      onPressed: allIds.isEmpty
                                          ? null
                                          : () => cubit.selectAllPayloadApis(allIds),
                                      child: const Text('All'),
                                    ),
                                    TextButton(
                                      onPressed: selected.isEmpty
                                          ? null
                                          : cubit.clearPayloadApiSelection,
                                      child: const Text('Clear'),
                                    ),
                                    TextButton(
                                      onPressed: state.loading || selected.isEmpty
                                          ? null
                                          : () => _confirmDeleteSelected(context, cubit),
                                      child: Text('Delete (${selected.length})'),
                                    ),
                                  ],
                                ),
                              ),
                              for (final r in rows)
                                ListTile(
                                  dense: true,
                                  leading: Checkbox(
                                    value: selected.contains('${r['api_id'] ?? ''}'),
                                    onChanged: '${r['api_id'] ?? ''}'.isEmpty
                                        ? null
                                        : (v) => cubit.togglePayloadApiSelection(
                                              '${r['api_id']}',
                                              selected: v == true,
                                            ),
                                  ),
                                  title: Text(
                                    _apiLabel(r, _requestOf(r)),
                                    style: const TextStyle(
                                      fontFamily: 'monospace',
                                      fontSize: 11,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  subtitle: Text(
                                    '${r['api_id'] ?? ''}',
                                    style: const TextStyle(fontSize: 10),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  trailing: TextButton(
                                    onPressed: state.loading
                                        ? null
                                        : () => _editRow(context, cubit, r),
                                    child: const Text('Edit'),
                                  ),
                                ),
                            ],
                          ),
                          if (summary?['from_generate'] == true)
                            ExpansionTile(
                              title: Text(
                                'Generate attempt details ($maxAttempts max)',
                                style: Theme.of(context).textTheme.labelLarge,
                              ),
                              children: [
                                for (final r in rows.take(5))
                                  QaJsonBlock(
                                    label: '${r['method']} ${r['path']}',
                                    value: r['attempts'] ?? r['error'],
                                  ),
                              ],
                            ),
                        ],
                      ),
          ),
        ],
      ),
    );
  }
}
