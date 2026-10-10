import 'dart:convert';

import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';
import '../widgets/qa_json_block.dart';
import 'datasets_apis_table.dart';
import 'datasets_values_panel.dart';

/// API rows table + edit/delete actions for Specs Datasets.
class DatasetsRowsList extends StatefulWidget {
  const DatasetsRowsList({
    super.key,
    required this.state,
    required this.cubit,
    required this.rows,
    required this.bySection,
  });

  final SpecsState state;
  final SpecsCubit cubit;
  final List<Map<String, dynamic>> rows;
  final Map<String, List<DatasetsValueHit>> bySection;

  @override
  State<DatasetsRowsList> createState() => _DatasetsRowsListState();
}

class _DatasetsRowsListState extends State<DatasetsRowsList> {
  bool _showValues = false;

  Future<void> _confirmDeleteSelected(BuildContext context) async {
    final n = widget.state.selectedPayloadApiIds.length;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete selected APIs'),
        content: Text(
          'Remove $n API(s) from payload set '
          'v${widget.state.selectedPayloadVersion}?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (ok == true) await widget.cubit.deleteSelectedPayloadApis();
  }

  Future<void> _editRow(
    BuildContext context,
    Map<String, dynamic> row,
  ) async {
    final apiId = '${row['api_id'] ?? ''}';
    if (apiId.isEmpty) return;
    final req = DatasetsValuesPanel.requestOf(row);
    final resp = row['response'] is Map
        ? Map<String, dynamic>.from(row['response'] as Map)
        : <String, dynamic>{};
    final reqCtrl = TextEditingController(
      text: const JsonEncoder.withIndent('  ').convert(req),
    );
    final respCtrl = TextEditingController(
      text: resp.isEmpty
          ? '{}'
          : const JsonEncoder.withIndent('  ').convert(resp),
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
                    labelText:
                        'request values (path_params / query / headers / body)',
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
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (saved != true) return;
    try {
      final request =
          Map<String, dynamic>.from(jsonDecode(reqCtrl.text) as Map);
      final responseRaw = jsonDecode(respCtrl.text);
      final response = responseRaw is Map
          ? Map<String, dynamic>.from(responseRaw)
          : <String, dynamic>{};
      await widget.cubit.editPayloadSetApi(
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

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final cubit = widget.cubit;
    final rows = widget.rows;
    final selected = state.selectedPayloadApiIds;
    final busy = state.payloadListLoading || state.payloadRowsLoading;
    final summary = state.generateSummary;
    const maxAttempts = 3;
    final allIds = [
      for (final r in rows)
        if ('${r['api_id'] ?? ''}'.isNotEmpty) '${r['api_id']}',
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Wrap(
            spacing: 6,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                'APIs (${rows.length})',
                style: Theme.of(context).textTheme.labelLarge,
              ),
              TextButton(
                onPressed: allIds.isEmpty
                    ? null
                    : () => cubit.selectAllPayloadApis(allIds),
                child: const Text('All'),
              ),
              TextButton(
                onPressed:
                    selected.isEmpty ? null : cubit.clearPayloadApiSelection,
                child: const Text('Clear'),
              ),
              TextButton(
                onPressed: busy || selected.isEmpty
                    ? null
                    : () => _confirmDeleteSelected(context),
                child: Text('Delete (${selected.length})'),
              ),
              FilterChip(
                label: const Text('Values'),
                selected: _showValues,
                visualDensity: VisualDensity.compact,
                onSelected: (v) => setState(() => _showValues = v),
              ),
            ],
          ),
        ),
        Expanded(
          child: DatasetsApisTable(
            state: state,
            cubit: cubit,
            rows: rows,
            onEdit: _editRow,
          ),
        ),
        if (_showValues && widget.bySection.isNotEmpty) ...[
          const Divider(),
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 220),
            child: SingleChildScrollView(
              child: DatasetsValuesPanel(hitsBySection: widget.bySection),
            ),
          ),
        ],
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
    );
  }
}
