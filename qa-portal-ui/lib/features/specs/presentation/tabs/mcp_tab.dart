import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';
import '../shell/method_colors.dart';
import '../widgets/qa_json_block.dart';

class SpecsMcpTab extends StatelessWidget {
  const SpecsMcpTab({required this.state});

  final SpecsState state;

  Map<String, dynamic>? _lastResultFor(String toolName) {
    final report = state.mcpToolReport;
    if (report == null) return null;
    final results = report['results'];
    if (results is! List) return null;
    for (final raw in results.reversed) {
      if (raw is Map && '${raw['tool'] ?? ''}' == toolName) {
        return Map<String, dynamic>.from(raw);
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<SpecsCubit>();
    final summary = state.mcpSummary;
    final tools = state.mcpTools;
    final report = state.mcpToolReport;
    final mapped = summary == null
        ? const <dynamic>[]
        : (summary['mapped'] is List ? summary['mapped'] as List : const []);
    final skipped = summary == null
        ? const <dynamic>[]
        : (summary['skipped'] is List ? summary['skipped'] as List : const []);
    final busy = state.loading || state.mcpRunning;

    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'MCP tools (${tools.length})',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              TextButton(
                onPressed: busy || state.selectedService == null
                    ? null
                    : cubit.refreshOpenapiTools,
                child: const Text('Refresh'),
              ),
              TextButton(
                onPressed: busy || tools.isEmpty
                    ? null
                    : () => cubit.runAllMcpTools(selectedOnly: true),
                child: const Text('Run selected'),
              ),
              FilledButton(
                onPressed: busy || tools.isEmpty
                    ? null
                    : () => cubit.runAllMcpTools(selectedOnly: false),
                child: state.mcpRunning
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Run all'),
              ),
            ],
          ),
          Text(
            'Same OpenAPI ops as APIs / Swagger. Tap row → Test. Run executes via OpenAPI tools.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppColors.textSecondaryDark,
                ),
          ),
          if (tools.isNotEmpty)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: busy
                    ? null
                    : state.selectedMcpToolNames.length == tools.length
                        ? cubit.clearMcpToolSelection
                        : cubit.selectAllMcpTools,
                child: Text(
                  state.selectedMcpToolNames.length == tools.length
                      ? 'Clear selection'
                      : 'Select all',
                ),
              ),
            ),
          const SizedBox(height: 4),
          Expanded(
            flex: 3,
            child: tools.isEmpty
                ? Center(
                    child: Text(
                      busy
                          ? 'Loading tools…'
                          : 'No tools yet — select a service or Refresh.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  )
                : ListView.separated(
                    itemCount: tools.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (_, i) {
                      final t = tools[i];
                      final method = '${t['method'] ?? 'GET'}'.toUpperCase();
                      final path = '${t['path'] ?? ''}';
                      final name = '${t['name'] ?? t['op_id'] ?? ''}';
                      final desc = '${t['description'] ?? ''}';
                      final checked = state.selectedMcpToolNames.contains(name);
                      final last = _lastResultFor(name);
                      final lastOk = last?['ok'] == true;
                      final lastStatus = last?['status'];
                      return ListTile(
                        dense: true,
                        onTap: () => cubit.pickTool(t),
                        leading: Checkbox(
                          value: checked,
                          onChanged: busy
                              ? null
                              : (v) => cubit.toggleMcpToolSelection(
                                    name,
                                    selected: v == true,
                                  ),
                        ),
                        title: Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: methodBg(method),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                method,
                                style: TextStyle(
                                  color: methodFg(method),
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                path,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 12,
                                ),
                              ),
                            ),
                            if (last != null)
                              Padding(
                                padding: const EdgeInsets.only(left: 4),
                                child: Chip(
                                  visualDensity: VisualDensity.compact,
                                  label: Text(
                                    lastOk ? 'OK $lastStatus' : 'FAIL ${lastStatus ?? ''}',
                                    style: const TextStyle(fontSize: 10),
                                  ),
                                  backgroundColor: (lastOk
                                          ? const Color(0xFF22C55E)
                                          : const Color(0xFFEF4444))
                                      .withValues(alpha: 0.2),
                                ),
                              ),
                          ],
                        ),
                        subtitle: Text(
                          desc.isNotEmpty ? desc : name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        trailing: IconButton(
                          tooltip: 'Run tool',
                          icon: const Icon(Icons.play_arrow, size: 20),
                          onPressed: busy ? null : () => cubit.runMcpTool(t),
                        ),
                      );
                    },
                  ),
          ),
          if (report != null) ...[
            const Divider(height: 12),
            Text('Report', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 4),
            Wrap(
              spacing: 8,
              children: [
                Chip(label: Text('passed: ${report['passed'] ?? 0}')),
                Chip(label: Text('failed: ${report['failed'] ?? 0}')),
                Chip(label: Text('total: ${report['total'] ?? 0}')),
                if (state.mcpRunning && report['progress'] != null)
                  Chip(label: Text('running ${report['progress']}')),
              ],
            ),
            const SizedBox(height: 4),
            Expanded(
              flex: 2,
              child: _McpReportList(report: report),
            ),
          ],
          const Divider(height: 12),
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text(
              'Portfolio assist',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton(
                    onPressed: busy || state.selectedService == null
                        ? null
                        : cubit.prepareMcp,
                    child: const Text('Prepare MCP'),
                  ),
                  FilledButton.tonal(
                    onPressed: busy ? null : () => cubit.ensureWorking(),
                    child: const Text('Ensure + apply'),
                  ),
                  OutlinedButton(
                    onPressed: busy ? null : cubit.aiMakeWork,
                    child: const Text('AI: make call work'),
                  ),
                ],
              ),
              if (summary != null) ...[
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  children: [
                    Chip(label: Text('mapped: ${summary['mapped_count'] ?? 0}')),
                    Chip(
                      label: Text(
                        'skipped: ${summary['skipped_count'] ?? skipped.length}',
                      ),
                    ),
                    if (summary['portfolio_id'] != null)
                      Chip(label: Text('portfolio: ${summary['portfolio_id']}')),
                  ],
                ),
                SizedBox(
                  height: 120,
                  child: ListView(
                    children: [
                      for (final raw in mapped.take(20))
                        if (raw is Map)
                          ListTile(
                            dense: true,
                            title: Text(
                              '${raw['method'] ?? ''} ${raw['path'] ?? ''}',
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
            ],
          ),
        ],
      ),
    );
  }
}

class _McpReportList extends StatelessWidget {
  const _McpReportList({required this.report});

  final Map<String, dynamic> report;

  @override
  Widget build(BuildContext context) {
    final results = report['results'] is List ? report['results'] as List : const [];
    if (results.isEmpty) {
      return Text('No results', style: Theme.of(context).textTheme.bodySmall);
    }
    return ListView.builder(
      itemCount: results.length,
      itemBuilder: (_, i) {
        final raw = results[i];
        if (raw is! Map) return const SizedBox.shrink();
        final row = Map<String, dynamic>.from(raw);
        final ok = row['ok'] == true;
        final tool = '${row['tool'] ?? ''}';
        final method = '${row['method'] ?? ''}';
        final path = '${row['path'] ?? ''}';
        final status = row['status'];
        final err = row['error'];
        final url = row['url'];
        return ExpansionTile(
          dense: true,
          leading: Icon(
            ok ? Icons.check_circle : Icons.error,
            color: ok ? const Color(0xFF22C55E) : const Color(0xFFEF4444),
            size: 18,
          ),
          title: Text(
            tool.isNotEmpty ? tool : '$method $path',
            style: const TextStyle(fontSize: 12, fontFamily: 'monospace'),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          subtitle: Text(
            [
              if (method.isNotEmpty || path.isNotEmpty) '$method $path',
              'status: ${status ?? '—'}',
              if (err != null) 'error: $err',
            ].join(' · '),
            style: Theme.of(context).textTheme.bodySmall,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          children: [
            if (url != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
                child: SelectableText(
                  '$url',
                  style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
                ),
              ),
            QaJsonBlock(label: 'Arguments used', value: row['arguments_used']),
            if (row['arguments_used'] is Map &&
                (row['arguments_used'] as Map).isEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
                child: Text(
                  'No payload args matched this method/path in any payload set. '
                  'Activate a richer set (e.g. invent-llm-dev) or Ensure the API first.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.amber,
                      ),
                ),
              ),
            QaJsonBlock(label: 'Response body', value: row['body'] ?? row['error']),
          ],
        );
      },
    );
  }
}
