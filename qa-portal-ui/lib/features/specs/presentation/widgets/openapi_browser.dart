import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

/// Native OpenAPI browser for desktop (replaces Swagger iframe stub).
class OpenApiBrowser extends StatefulWidget {
  const OpenApiBrowser({
    super.key,
    required this.spec,
    required this.service,
    required this.environment,
    required this.tryBase,
    this.token,
    this.onUseInTest,
    this.onRefresh,
  });

  final Map<String, dynamic> spec;
  final String service;
  final String environment;
  final String tryBase;
  final String? token;
  final void Function(Map<String, dynamic> draft)? onUseInTest;
  final VoidCallback? onRefresh;

  @override
  State<OpenApiBrowser> createState() => _OpenApiBrowserState();
}

class _Op {
  const _Op({
    required this.method,
    required this.path,
    required this.summary,
    required this.operationId,
    required this.raw,
  });

  final String method;
  final String path;
  final String summary;
  final String operationId;
  final Map<String, dynamic> raw;
}

class _OpenApiBrowserState extends State<OpenApiBrowser> {
  final _filter = TextEditingController();
  _Op? _selected;
  late List<_Op> _ops;

  @override
  void initState() {
    super.initState();
    _ops = _parseOps(widget.spec);
    if (_ops.isNotEmpty) _selected = _ops.first;
  }

  @override
  void didUpdateWidget(covariant OpenApiBrowser oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.spec != widget.spec) {
      _ops = _parseOps(widget.spec);
      _selected = _ops.isEmpty
          ? null
          : _ops.cast<_Op?>().firstWhere(
                (o) =>
                    o?.method == _selected?.method &&
                    o?.path == _selected?.path,
                orElse: () => _ops.first,
              );
    }
  }

  @override
  void dispose() {
    _filter.dispose();
    super.dispose();
  }

  List<_Op> _parseOps(Map<String, dynamic> spec) {
    final paths = spec['paths'];
    if (paths is! Map) return const [];
    final out = <_Op>[];
    final methods = const {
      'get',
      'post',
      'put',
      'patch',
      'delete',
      'head',
      'options',
    };
    for (final e in paths.entries) {
      final path = '${e.key}';
      final item = e.value;
      if (item is! Map) continue;
      for (final m in item.entries) {
        final method = '${m.key}'.toLowerCase();
        if (!methods.contains(method)) continue;
        final op = m.value is Map
            ? Map<String, dynamic>.from(m.value as Map)
            : <String, dynamic>{};
        out.add(
          _Op(
            method: method.toUpperCase(),
            path: path,
            summary: '${op['summary'] ?? op['operationId'] ?? ''}',
            operationId: '${op['operationId'] ?? ''}',
            raw: op,
          ),
        );
      }
    }
    out.sort((a, b) {
      final c = a.path.compareTo(b.path);
      return c != 0 ? c : a.method.compareTo(b.method);
    });
    return out;
  }

  List<_Op> get _visible {
    final q = _filter.text.trim().toLowerCase();
    if (q.isEmpty) return _ops;
    return [
      for (final o in _ops)
        if (o.path.toLowerCase().contains(q) ||
            o.method.toLowerCase().contains(q) ||
            o.summary.toLowerCase().contains(q) ||
            o.operationId.toLowerCase().contains(q))
          o,
    ];
  }

  Map<String, dynamic> _draftFor(_Op op) {
    final params = op.raw['parameters'];
    final pathParams = <String, dynamic>{};
    final query = <String, dynamic>{};
    final headers = <String, dynamic>{};
    if (params is List) {
      for (final p in params) {
        if (p is! Map) continue;
        final name = '${p['name'] ?? ''}';
        if (name.isEmpty) continue;
        final loc = '${p['in'] ?? ''}';
        final ex = p['example'] ??
            (p['schema'] is Map ? (p['schema'] as Map)['example'] : null) ??
            '';
        if (loc == 'path') {
          pathParams[name] = ex;
        } else if (loc == 'query') {
          query[name] = ex;
        } else if (loc == 'header') {
          headers[name] = ex;
        }
      }
    }
    dynamic body;
    final rb = op.raw['requestBody'];
    if (rb is Map) {
      final content = rb['content'];
      if (content is Map && content['application/json'] is Map) {
        final schema = content['application/json']['schema'];
        final example = content['application/json']['example'];
        body = example ?? (schema is Map ? schema['example'] : null) ?? {};
      }
    }
    return {
      'method': op.method,
      'path': op.path,
      'path_params': pathParams,
      'query': query,
      'headers': headers,
      if (body != null) 'body': body,
      'operationId': op.operationId,
    };
  }

  Future<void> _openDocs() async {
    final base = widget.tryBase.replaceAll(RegExp(r'/$'), '');
    final uri = Uri.parse('$base/docs');
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  Color _methodColor(BuildContext context, String method) {
    final cs = Theme.of(context).colorScheme;
    switch (method) {
      case 'GET':
        return Colors.green.shade700;
      case 'POST':
        return Colors.blue.shade700;
      case 'PUT':
      case 'PATCH':
        return Colors.orange.shade800;
      case 'DELETE':
        return cs.error;
      default:
        return cs.onSurfaceVariant;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final selected = _selected;
    final visible = _visible;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 320,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 8, 8, 4),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _filter,
                        decoration: const InputDecoration(
                          hintText: 'Filter operations',
                          isDense: true,
                          border: OutlineInputBorder(),
                          prefixIcon: Icon(Icons.search, size: 18),
                        ),
                        onChanged: (_) => setState(() {}),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Reload OpenAPI',
                      onPressed: widget.onRefresh,
                      icon: const Icon(Icons.refresh, size: 20),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    '${widget.service} · ${widget.environment} · ${_ops.length} ops',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
              const Divider(height: 12),
              Expanded(
                child: visible.isEmpty
                    ? const Center(child: Text('No operations'))
                    : ListView.builder(
                        itemCount: visible.length,
                        itemBuilder: (ctx, i) {
                          final op = visible[i];
                          final sel = selected?.method == op.method &&
                              selected?.path == op.path;
                          return ListTile(
                            dense: true,
                            selected: sel,
                            title: Row(
                              children: [
                                SizedBox(
                                  width: 56,
                                  child: Text(
                                    op.method,
                                    style: theme.textTheme.labelSmall?.copyWith(
                                      color: _methodColor(context, op.method),
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ),
                                Expanded(
                                  child: Text(
                                    op.path,
                                    overflow: TextOverflow.ellipsis,
                                    style: theme.textTheme.bodySmall,
                                  ),
                                ),
                              ],
                            ),
                            subtitle: op.summary.isEmpty
                                ? null
                                : Text(
                                    op.summary,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                            onTap: () => setState(() => _selected = op),
                          );
                        },
                      ),
              ),
            ],
          ),
        ),
        const VerticalDivider(width: 1),
        Expanded(
          child: selected == null
              ? const Center(child: Text('Select an operation'))
              : Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        children: [
                          Text(
                            selected.method,
                            style: theme.textTheme.titleMedium?.copyWith(
                              color: _methodColor(context, selected.method),
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: SelectableText(
                              selected.path,
                              style: theme.textTheme.titleMedium,
                            ),
                          ),
                        ],
                      ),
                      if (selected.summary.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        Text(selected.summary),
                      ],
                      if (selected.operationId.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          'operationId: ${selected.operationId}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          FilledButton.icon(
                            onPressed: widget.onUseInTest == null
                                ? null
                                : () =>
                                    widget.onUseInTest!(_draftFor(selected)),
                            icon: const Icon(Icons.science_outlined, size: 18),
                            label: const Text('Use in Test'),
                          ),
                          OutlinedButton.icon(
                            onPressed: () async {
                              final draft = _draftFor(selected);
                              await Clipboard.setData(
                                ClipboardData(
                                  text:
                                      '${draft['method']} ${draft['path']}\n'
                                      '$draft',
                                ),
                              );
                              if (!context.mounted) return;
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Copied operation draft'),
                                ),
                              );
                            },
                            icon: const Icon(Icons.copy, size: 18),
                            label: const Text('Copy'),
                          ),
                          OutlinedButton.icon(
                            onPressed: _openDocs,
                            icon: const Icon(Icons.open_in_new, size: 18),
                            label: const Text('Open docs'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Text('Parameters', style: theme.textTheme.titleSmall),
                      const SizedBox(height: 8),
                      Expanded(
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            border: Border.all(
                              color: theme.colorScheme.outlineVariant,
                            ),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: SingleChildScrollView(
                            padding: const EdgeInsets.all(12),
                            child: SelectableText(
                              _formatParams(selected),
                              style: theme.textTheme.bodySmall?.copyWith(
                                fontFamily: 'Consolas',
                              ),
                            ),
                          ),
                        ),
                      ),
                      if ((widget.token ?? '').isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text(
                          'Try token present for ${widget.environment}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.primary,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
        ),
      ],
    );
  }

  String _formatParams(_Op op) {
    final buf = StringBuffer();
    final params = op.raw['parameters'];
    if (params is List && params.isNotEmpty) {
      for (final p in params) {
        if (p is! Map) continue;
        buf.writeln(
          '- [${p['in']}] ${p['name']}'
          '${p['required'] == true ? ' *' : ''}'
          '${p['description'] != null ? ' — ${p['description']}' : ''}',
        );
      }
    } else {
      buf.writeln('(no parameters)');
    }
    final rb = op.raw['requestBody'];
    if (rb != null) {
      buf.writeln();
      buf.writeln('requestBody:');
      buf.writeln(rb.toString());
    }
    return buf.toString();
  }
}
