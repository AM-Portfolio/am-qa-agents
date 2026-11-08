import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/flows_cubit.dart';
import '../utils/flows_field_paths.dart';

/// Manual field map: previous response paths → next card inputs.
Future<void> showFlowFieldMapper(BuildContext context) async {
  final cubit = context.read<FlowsCubit>();
  final state = cubit.state;
  final selectedId = state.selectedLogNodeId;
  if (selectedId == null || selectedId == '__manual_trigger__') {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Select the next API card first')),
    );
    return;
  }

  final prevId = cubit.predecessorNodeId(selectedId);
  if (prevId == null || prevId == '__manual_trigger__') {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('No previous API step — connect a card before this one'),
      ),
    );
    return;
  }

  final prev = cubit.nodeById(prevId);
  final next = cubit.nodeById(selectedId);
  if (prev == null || next == null) return;

  final response = cubit.responseBodyForNode(prevId);
  final paths = flattenResponsePaths(response);
  final slots = inputSlotsForNode(next);

  // Seed rows from existing capture on previous node.
  final existing = <FieldMappingRow>[];
  final cap = prev['capture'];
  if (cap is Map) {
    for (final e in cap.entries) {
      final name = '${e.key}';
      final raw = e.value;
      final path = raw is List && raw.isNotEmpty
          ? '${raw.first}'
          : '$raw';
      var kind = 'query';
      final bp = next['bind_path'];
      final bq = next['bind_query'];
      final bo = next['body_override'];
      if (bp is Map && bp.containsKey(name)) {
        kind = 'path';
      } else if (bo is Map && bo.containsKey(name)) {
        kind = 'body';
      } else if (bq is Map && bq.containsKey(name)) {
        kind = 'query';
      } else if (slots.any((s) => s.name == name)) {
        kind = slots.firstWhere((s) => s.name == name).kind;
      }
      existing.add(
        FieldMappingRow(
          responsePath: path,
          inputName: name,
          inputKind: kind,
        ),
      );
    }
  }

  await showDialog<void>(
    context: context,
    builder: (ctx) => _FieldMapperDialog(
      prevId: prevId,
      nextId: selectedId,
      prevLabel: '${prev['label'] ?? prevId}',
      nextLabel: '${next['label'] ?? selectedId}',
      responsePaths: paths,
      slots: slots,
      initialRows: existing,
      hasResponse: response != null,
      onApply: (rows) {
        cubit.applyFieldMappings(
          previousNodeId: prevId,
          nextNodeId: selectedId,
          rows: rows,
        );
      },
    ),
  );
}

class _FieldMapperDialog extends StatefulWidget {
  const _FieldMapperDialog({
    required this.prevId,
    required this.nextId,
    required this.prevLabel,
    required this.nextLabel,
    required this.responsePaths,
    required this.slots,
    required this.initialRows,
    required this.hasResponse,
    required this.onApply,
  });

  final String prevId;
  final String nextId;
  final String prevLabel;
  final String nextLabel;
  final List<String> responsePaths;
  final List<FlowInputSlot> slots;
  final List<FieldMappingRow> initialRows;
  final bool hasResponse;
  final ValueChanged<List<FieldMappingRow>> onApply;

  @override
  State<_FieldMapperDialog> createState() => _FieldMapperDialogState();
}

class _FieldMapperDialogState extends State<_FieldMapperDialog> {
  late List<FieldMappingRow> _rows;
  String? _pickedPath;

  @override
  void initState() {
    super.initState();
    _rows = [
      for (final r in widget.initialRows)
        FieldMappingRow(
          responsePath: r.responsePath,
          inputName: r.inputName,
          inputKind: r.inputKind,
        ),
    ];
  }

  void _addRow({String? path, FlowInputSlot? slot}) {
    setState(() {
      _rows.add(
        FieldMappingRow(
          responsePath: path ?? _pickedPath ?? '',
          inputName: slot?.name ?? '',
          inputKind: slot?.kind ?? 'query',
        ),
      );
      _pickedPath = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    return AlertDialog(
      title: Text('Map fields · ${widget.prevLabel} → ${widget.nextLabel}'),
      content: SizedBox(
        width: 720,
        height: 460,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Pick a response field on the left, then an input on the right '
              '(or edit rows below). Saves capture on the previous step and '
              'bind on this card.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: cs.onSurfaceVariant,
              ),
            ),
            if (!widget.hasResponse) ...[
              const SizedBox(height: 8),
              Text(
                'No response yet for ${widget.prevId} — Run or Quick-test that '
                'step first so fields appear. You can still type paths manually.',
                style: theme.textTheme.bodySmall?.copyWith(color: cs.error),
              ),
            ],
            const SizedBox(height: 12),
            Expanded(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Expanded(
                    child: _PathList(
                      title: 'Response fields',
                      subtitle: widget.prevId,
                      items: widget.responsePaths,
                      selected: _pickedPath,
                      emptyHint: 'No fields — run previous step',
                      onTap: (p) => setState(() => _pickedPath = p),
                      onUse: (p) => _addRow(path: p),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _SlotList(
                      title: 'Next inputs',
                      subtitle: widget.nextId,
                      slots: widget.slots,
                      onTap: (s) {
                        if (_pickedPath != null && _pickedPath!.isNotEmpty) {
                          _addRow(path: _pickedPath, slot: s);
                        } else {
                          _addRow(slot: s);
                        }
                      },
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Text('Mappings', style: theme.textTheme.labelLarge),
            const SizedBox(height: 6),
            SizedBox(
              height: 140,
              child: _rows.isEmpty
                  ? Center(
                      child: Text(
                        'No mappings yet',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: cs.onSurfaceVariant,
                        ),
                      ),
                    )
                  : ListView.builder(
                      itemCount: _rows.length,
                      itemBuilder: (context, i) {
                        final row = _rows[i];
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Row(
                            children: [
                              Expanded(
                                flex: 3,
                                child: TextFormField(
                                  initialValue: row.responsePath,
                                  decoration: const InputDecoration(
                                    labelText: 'Response path',
                                    isDense: true,
                                    border: OutlineInputBorder(),
                                  ),
                                  onChanged: (v) => row.responsePath = v,
                                ),
                              ),
                              const Padding(
                                padding: EdgeInsets.symmetric(horizontal: 8),
                                child: Icon(Icons.arrow_forward, size: 16),
                              ),
                              Expanded(
                                flex: 2,
                                child: TextFormField(
                                  initialValue: row.inputName,
                                  decoration: const InputDecoration(
                                    labelText: 'Input name',
                                    isDense: true,
                                    border: OutlineInputBorder(),
                                  ),
                                  onChanged: (v) => row.inputName = v,
                                ),
                              ),
                              const SizedBox(width: 6),
                              SizedBox(
                                width: 100,
                                child: DropdownButtonFormField<String>(
                                  initialValue: row.inputKind,
                                  isDense: true,
                                  decoration: const InputDecoration(
                                    labelText: 'As',
                                    isDense: true,
                                    border: OutlineInputBorder(),
                                  ),
                                  items: const [
                                    DropdownMenuItem(
                                      value: 'path',
                                      child: Text('path'),
                                    ),
                                    DropdownMenuItem(
                                      value: 'query',
                                      child: Text('query'),
                                    ),
                                    DropdownMenuItem(
                                      value: 'body',
                                      child: Text('body'),
                                    ),
                                  ],
                                  onChanged: (v) {
                                    if (v == null) return;
                                    setState(() => row.inputKind = v);
                                  },
                                ),
                              ),
                              IconButton(
                                tooltip: 'Remove',
                                onPressed: () =>
                                    setState(() => _rows.removeAt(i)),
                                icon: const Icon(Icons.close, size: 18),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
            ),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () => _addRow(),
                icon: const Icon(Icons.add, size: 16),
                label: const Text('Add mapping'),
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            widget.onApply(List<FieldMappingRow>.from(_rows));
            Navigator.of(context).pop();
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Field map saved — Save graph to persist'),
              ),
            );
          },
          child: const Text('Apply map'),
        ),
      ],
    );
  }
}

class _PathList extends StatelessWidget {
  const _PathList({
    required this.title,
    required this.subtitle,
    required this.items,
    required this.selected,
    required this.emptyHint,
    required this.onTap,
    required this.onUse,
  });

  final String title;
  final String subtitle;
  final List<String> items;
  final String? selected;
  final String emptyHint;
  final ValueChanged<String> onTap;
  final ValueChanged<String> onUse;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: cs.outlineVariant),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 8, 10, 4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: theme.textTheme.labelLarge),
                Text(
                  subtitle,
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: cs.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: items.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(
                        emptyHint,
                        textAlign: TextAlign.center,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: cs.onSurfaceVariant,
                        ),
                      ),
                    ),
                  )
                : ListView.builder(
                    itemCount: items.length,
                    itemBuilder: (context, i) {
                      final p = items[i];
                      final sel = p == selected;
                      return ListTile(
                        dense: true,
                        selected: sel,
                        title: Text(
                          p,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.bodySmall?.copyWith(
                            fontFamily: 'monospace',
                          ),
                        ),
                        trailing: IconButton(
                          tooltip: 'Use in mapping',
                          icon: const Icon(Icons.add_circle_outline, size: 18),
                          onPressed: () => onUse(p),
                        ),
                        onTap: () => onTap(p),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _SlotList extends StatelessWidget {
  const _SlotList({
    required this.title,
    required this.subtitle,
    required this.slots,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final List<FlowInputSlot> slots;
  final ValueChanged<FlowInputSlot> onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: cs.outlineVariant),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 8, 10, 4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: theme.textTheme.labelLarge),
                Text(
                  subtitle,
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: cs.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView.builder(
              itemCount: slots.length,
              itemBuilder: (context, i) {
                final s = slots[i];
                return ListTile(
                  dense: true,
                  title: Text(s.name, style: theme.textTheme.bodyMedium),
                  subtitle: Text(
                    s.kind + (s.hint != null ? ' · ${s.hint}' : ''),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: Chip(
                    label: Text(s.kind),
                    visualDensity: VisualDensity.compact,
                    padding: EdgeInsets.zero,
                    labelStyle: theme.textTheme.labelSmall,
                  ),
                  onTap: () => onTap(s),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
