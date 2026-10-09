import 'dart:convert';

import 'package:flutter/material.dart';

class FlowsRunLogsPanel extends StatelessWidget {
  const FlowsRunLogsPanel({
    required this.onSelect,
    required this.onFilter,
    required this.onOpenExecution,
    this.execution,
    this.graph,
    this.selectedNodeId,
    this.nodeQuickResults = const {},
    this.recentExecutions = const [],
    this.filterStatus = '',
    this.filterFlowId = '',
    this.filterEnv = '',
  });

  final Map<String, dynamic>? graph;
  final Map<String, dynamic>? execution;
  final String? selectedNodeId;
  final Map<String, Map<String, dynamic>> nodeQuickResults;
  final ValueChanged<String> onSelect;
  final List<Map<String, dynamic>> recentExecutions;
  final String filterStatus;
  final String filterFlowId;
  final String filterEnv;
  final void Function({String? status, String? flowId, String? env}) onFilter;
  final ValueChanged<String> onOpenExecution;

  List<FlowLogEntry> _entries() {
    final ex = execution;
    final nodeStates = ex?['nodes'];
    final byId = <String, Map>{};
    if (nodeStates is Map) {
      for (final e in nodeStates.entries) {
        if (e.value is Map) byId['${e.key}'] = Map<String, dynamic>.from(e.value as Map);
      }
    }
    // Quick-test peek overlays / fills when no full execution yet.
    for (final e in nodeQuickResults.entries) {
      final q = e.value;
      final prev = byId[e.key] ?? <String, dynamic>{};
      byId[e.key] = {
        ...prev,
        if (q['status'] != null) 'status': q['status'],
        if (q['http_status'] != null) 'http_status': q['http_status'],
        if (q['request'] != null) 'request': q['request'],
        if (q['response'] != null) 'response': q['response'],
        if (q['error'] != null) 'error': q['error'],
        if (q['request'] is Map && (q['request'] as Map)['url'] != null)
          'url': (q['request'] as Map)['url'],
        if (q['request'] is Map && (q['request'] as Map)['method'] != null)
          'method': (q['request'] as Map)['method'],
        if (q['request'] is Map && (q['request'] as Map)['path'] != null)
          'path': (q['request'] as Map)['path'],
      };
    }
    if (ex == null && byId.isEmpty) return const [];
    final order = <String>[];
    final gNodes = graph?['nodes'];
    if (gNodes is List) {
      for (final raw in gNodes) {
        if (raw is Map) {
          final id = '${raw['id']}';
          order.add(id);
          byId.putIfAbsent(id, () => {});
        }
      }
    }
    for (final id in byId.keys) {
      if (!order.contains(id)) order.add(id);
    }
    return [
      for (final id in order)
        FlowLogEntry(
          id: id,
          label: _labelFor(id, byId[id], gNodes),
          status: '${byId[id]?['status'] ?? ''}',
          durationMs: byId[id]?['duration_ms'],
          httpStatus: byId[id]?['http_status'],
          method: '${byId[id]?['method'] ?? ''}',
          url: '${byId[id]?['url'] ?? ''}',
          path: '${byId[id]?['path'] ?? ''}',
          request: byId[id]?['request'],
          response: byId[id]?['response'],
          error: byId[id]?['error'],
        ),
    ];
  }

  String _labelFor(String id, Map? st, dynamic gNodes) {
    final fromEv = st?['label']?.toString();
    if (fromEv != null && fromEv.isNotEmpty) return fromEv;
    if (gNodes is List) {
      for (final raw in gNodes) {
        if (raw is Map && '${raw['id']}' == id) {
          final l = '${raw['label'] ?? ''}';
          if (l.isNotEmpty) return l;
        }
      }
    }
    return id.contains('::') ? id.split('::').last : id;
  }

  @override
  Widget build(BuildContext context) {
    final entries = _entries();
    final selected = entries.cast<FlowLogEntry?>().firstWhere(
          (e) => e?.id == selectedNodeId,
          orElse: () => entries.isNotEmpty ? entries.first : null,
        );
    final summary = execution?['summary'];
    final status = '${execution?['status'] ?? ''}';
    String summaryLine = status.isEmpty ? 'No execution selected' : status;
    if (summary is Map) {
      summaryLine =
          '$status · passed=${summary['passed']} · me_plan=${summary['me_plan']} · plans=${summary['plans_count']}';
    } else if (status.isEmpty && nodeQuickResults.isNotEmpty) {
      summaryLine = 'Quick-test results · ${nodeQuickResults.length} node(s)';
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
          child: Wrap(
            spacing: 8,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SizedBox(
                width: 120,
                child: DropdownButtonFormField<String>(
                  initialValue: filterStatus,
                  isDense: true,
                  decoration: const InputDecoration(
                    labelText: 'Status',
                    isDense: true,
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(value: '', child: Text('Any')),
                    DropdownMenuItem(value: 'running', child: Text('running')),
                    DropdownMenuItem(value: 'finished', child: Text('finished')),
                    DropdownMenuItem(value: 'failed', child: Text('failed')),
                    DropdownMenuItem(value: 'error', child: Text('error')),
                    DropdownMenuItem(value: 'stopped', child: Text('stopped')),
                  ],
                  onChanged: (v) => onFilter(status: v ?? ''),
                ),
              ),
              SizedBox(
                width: 160,
                child: TextFormField(
                  key: ValueKey('ex-flow-$filterFlowId'),
                  initialValue: filterFlowId,
                  decoration: const InputDecoration(
                    labelText: 'Flow id',
                    isDense: true,
                    border: OutlineInputBorder(),
                  ),
                  onFieldSubmitted: (v) => onFilter(flowId: v.trim()),
                ),
              ),
              SizedBox(
                width: 110,
                child: DropdownButtonFormField<String>(
                  initialValue: filterEnv,
                  isDense: true,
                  decoration: const InputDecoration(
                    labelText: 'Env',
                    isDense: true,
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(value: '', child: Text('Any')),
                    DropdownMenuItem(value: 'prod', child: Text('prod')),
                    DropdownMenuItem(value: 'preprod', child: Text('preprod')),
                    DropdownMenuItem(value: 'dev', child: Text('dev')),
                  ],
                  onChanged: (v) => onFilter(env: v ?? ''),
                ),
              ),
              Text(
                summaryLine,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        if (recentExecutions.isNotEmpty)
          SizedBox(
            height: 36,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: recentExecutions.length.clamp(0, 20),
              separatorBuilder: (_, __) => const SizedBox(width: 6),
              itemBuilder: (context, i) {
                final row = recentExecutions[i];
                final id = '${row['id']}';
                final short = id.length > 8 ? id.substring(0, 8) : id;
                final st = '${row['status'] ?? ''}';
                final fid = '${row['flow_id'] ?? ''}';
                final sel = id == '${execution?['id'] ?? ''}';
                return ActionChip(
                  label: Text('$short · $st · $fid', style: const TextStyle(fontSize: 11)),
                  onPressed: () => onOpenExecution(id),
                  backgroundColor: sel
                      ? Theme.of(context).colorScheme.primaryContainer
                      : null,
                );
              },
            ),
          ),
        Expanded(
          child: entries.isEmpty
              ? const Center(
                  child: Text(
                    'Run a flow, quick-test a node, or pick an execution above',
                  ),
                )
              : Row(
                  children: [
                    SizedBox(
                      width: 280,
                      child: ListView.builder(
                        itemCount: entries.length,
                        itemBuilder: (context, i) {
                          final e = entries[i];
                          final sel = e.id == (selected?.id);
                          return ListTile(
                            dense: true,
                            selected: sel,
                            leading: _runLogStatusIcon(e.status),
                            title: Text(
                              e.label,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            subtitle: Text(
                              [
                                if (e.status.isNotEmpty) e.status,
                                if (e.durationMs != null) '${e.durationMs}ms',
                                if (e.httpStatus != null) 'HTTP ${e.httpStatus}',
                              ].join(' · '),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.labelSmall,
                            ),
                            onTap: () => onSelect(e.id),
                          );
                        },
                      ),
                    ),
                    const VerticalDivider(width: 1),
                    Expanded(
                      child: selected == null
                          ? const Center(child: Text('Select a node'))
                          : DefaultTabController(
                              length: 3,
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  const TabBar(
                                    tabs: [
                                      Tab(text: 'Inputs'),
                                      Tab(text: 'Outputs'),
                                      Tab(text: 'Details'),
                                    ],
                                  ),
                                  Expanded(
                                    child: TabBarView(
                                      children: [
                                        FlowJsonPane(
                                          emptyLabel: 'No data emitted',
                                          value: selected.request,
                                        ),
                                        FlowJsonPane(
                                          emptyLabel: 'No data emitted',
                                          value:
                                              selected.error ?? selected.response,
                                        ),
                                        FlowDetailsPane(entry: selected),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                    ),
                  ],
                ),
        ),
      ],
    );
  }

  Widget _runLogStatusIcon(String status) {
    switch (status) {
      case 'ok':
        return const Icon(Icons.check_circle, color: Color(0xFF2E7D32), size: 20);
      case 'fail':
        return const Icon(Icons.error, color: Color(0xFFC62828), size: 20);
      case 'skipped':
        return const Icon(Icons.warning_amber, color: Color(0xFFF9A825), size: 20);
      case 'running':
        return const SizedBox(
          width: 18,
          height: 18,
          child: CircularProgressIndicator(strokeWidth: 2),
        );
      default:
        return const Icon(Icons.circle_outlined, size: 18);
    }
  }
}


class FlowLogEntry {
  const FlowLogEntry({
    required this.id,
    required this.label,
    required this.status,
    this.durationMs,
    this.httpStatus,
    this.method = '',
    this.url = '',
    this.path = '',
    this.request,
    this.response,
    this.error,
  });

  final String id;
  final String label;
  final String status;
  final Object? durationMs;
  final Object? httpStatus;
  final String method;
  final String url;
  final String path;
  final Object? request;
  final Object? response;
  final Object? error;
}


class FlowJsonPane extends StatelessWidget {
  const FlowJsonPane({required this.emptyLabel, this.value});

  final String emptyLabel;
  final Object? value;

  String _pretty() {
    if (value == null) return '';
    try {
      return const JsonEncoder.withIndent('  ').convert(value);
    } catch (_) {
      return value.toString();
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = _pretty();
    if (text.isEmpty) {
      return Center(
        child: Text(
          emptyLabel,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      );
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: SelectableText(
        text,
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: 12,
          color: Theme.of(context).colorScheme.onSurface,
        ),
      ),
    );
  }
}


class FlowDetailsPane extends StatelessWidget {
  const FlowDetailsPane({required this.entry});

  final FlowLogEntry entry;

  @override
  Widget build(BuildContext context) {
    final rows = <MapEntry<String, String>>[
      MapEntry('node_id', entry.id),
      MapEntry('status', entry.status),
      MapEntry('method', entry.method),
      MapEntry('path', entry.path),
      MapEntry('url', entry.url),
      MapEntry('http_status', '${entry.httpStatus ?? ''}'),
      MapEntry('duration_ms', '${entry.durationMs ?? ''}'),
    ];
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        for (final r in rows)
          if (r.value.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 110,
                    child: Text(
                      r.key,
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                  ),
                  Expanded(
                    child: SelectableText(
                      r.value,
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
            ),
      ],
    );
  }
}

