import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// One secret / field value reused across payload-set APIs.
class DatasetsValueHit {
  const DatasetsValueHit({
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

/// Collect + render reusable values from payload-set rows.
class DatasetsValuesPanel extends StatelessWidget {
  const DatasetsValuesPanel({
    super.key,
    required this.hitsBySection,
  });

  final Map<String, List<DatasetsValueHit>> hitsBySection;

  static const sectionOrder = [
    'domain',
    'path_params',
    'query',
    'headers',
    'body',
  ];

  static Map<String, dynamic> requestOf(Map<String, dynamic> r) {
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

  static String apiLabel(Map<String, dynamic> r, Map<String, dynamic> req) {
    final m = '${req['method'] ?? r['method'] ?? 'GET'}'.toUpperCase();
    final p = '${req['path'] ?? r['path'] ?? ''}';
    return '$m $p';
  }

  static void addMapValues({
    required Map<String, DatasetsValueHit> bag,
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
          addMapValues(
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
          bag[id] = DatasetsValueHit(
            section: section,
            key: name,
            value: s,
            apis: [apiLabel],
          );
        } else if (!prev.apis.contains(apiLabel)) {
          bag[id] = DatasetsValueHit(
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
        addMapValues(
          bag: bag,
          section: section,
          raw: raw[i],
          apiLabel: apiLabel,
          keyPrefix: keyPrefix.isEmpty ? '[$i]' : '$keyPrefix[$i]',
        );
      }
    }
  }

  static List<DatasetsValueHit> collectValues({
    required List<Map<String, dynamic>> rows,
    String? targetUrl,
  }) {
    final bag = <String, DatasetsValueHit>{};
    final domain = (targetUrl ?? '').trim();
    if (domain.isNotEmpty) {
      bag['domain|base_url|$domain'] = DatasetsValueHit(
        section: 'domain',
        key: 'base_url',
        value: domain,
        apis: const ['(workspace target)'],
      );
    }
    for (final r in rows) {
      final req = requestOf(r);
      final label = apiLabel(r, req);
      addMapValues(
        bag: bag,
        section: 'path_params',
        raw: req['path_params'] ?? req['pathParams'],
        apiLabel: label,
      );
      addMapValues(
        bag: bag,
        section: 'query',
        raw: req['query'] ?? req['query_params'],
        apiLabel: label,
      );
      addMapValues(
        bag: bag,
        section: 'headers',
        raw: req['headers'],
        apiLabel: label,
      );
      final body = req['body'] ?? r['body'];
      if (body is Map || body is List) {
        addMapValues(bag: bag, section: 'body', raw: body, apiLabel: label);
      } else if (body is String && body.trim().isNotEmpty) {
        try {
          final decoded = jsonDecode(body);
          addMapValues(bag: bag, section: 'body', raw: decoded, apiLabel: label);
        } catch (_) {
          final id = 'body|(raw)|$body';
          bag.putIfAbsent(
            id,
            () => DatasetsValueHit(
              section: 'body',
              key: '(raw)',
              value: body.length > 120 ? '${body.substring(0, 117)}…' : body,
              apis: [label],
            ),
          );
        }
      }
    }
    final list = bag.values.toList()
      ..sort((a, b) {
        final sa = sectionOrder.indexOf(a.section);
        final sb = sectionOrder.indexOf(b.section);
        final c = (sa < 0 ? 99 : sa).compareTo(sb < 0 ? 99 : sb);
        if (c != 0) return c;
        final kc = a.key.compareTo(b.key);
        if (kc != 0) return kc;
        return a.value.compareTo(b.value);
      });
    return list;
  }

  static Map<String, List<DatasetsValueHit>> groupBySection(
    List<DatasetsValueHit> values,
  ) {
    final bySection = <String, List<DatasetsValueHit>>{};
    for (final v in values) {
      bySection.putIfAbsent(v.section, () => []).add(v);
    }
    return bySection;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final section in sectionOrder)
          if (hitsBySection[section]?.isNotEmpty == true) ...[
            _sectionHeader(context, section, hitsBySection[section]!.length),
            for (final hit in hitsBySection[section]!)
              _ValueTile(hit: hit),
          ],
      ],
    );
  }

  Widget _sectionHeader(BuildContext context, String section, int count) {
    const labels = {
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
}

class _ValueTile extends StatelessWidget {
  const _ValueTile({required this.hit});

  final DatasetsValueHit hit;

  @override
  Widget build(BuildContext context) {
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
                              title: Text(
                                a,
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 12,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(ctx),
                        child: const Text('Close'),
                      ),
                    ],
                  ),
                );
              },
      ),
    );
  }
}
