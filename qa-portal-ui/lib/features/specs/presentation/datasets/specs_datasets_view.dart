import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/specs_cubit.dart';
import '../widgets/import_pickers.dart';
import 'datasets_rows_list.dart';
import 'datasets_values_panel.dart';

/// Primary Datasets destination — version dropdown + API rows.
class SpecsDatasetsView extends StatelessWidget {
  const SpecsDatasetsView({super.key, required this.state});

  final SpecsState state;

  List<Map<String, dynamic>> _rows() => state.generateResults;

  Future<void> _confirmDeleteVersion(
    BuildContext context,
    SpecsCubit cubit,
  ) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete entire version'),
        content: Text(
          'Permanently delete payload set v${state.selectedPayloadVersion} '
          'for ${state.selectedService}? This cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
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

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<SpecsCubit>();
    final summary = state.generateSummary;
    final rows = _rows();
    final values = DatasetsValuesPanel.collectValues(
      rows: rows,
      targetUrl: state.targetUrl,
    );
    final bySection = DatasetsValuesPanel.groupBySection(values);
    final busy = state.payloadListLoading || state.payloadRowsLoading;
    final sets = state.payloadSets;
    final selectedVer = state.selectedPayloadVersion;
    final activeVer = state.activePayloadVersion;
    final dense = TextButton.styleFrom(
      visualDensity: VisualDensity.compact,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      minimumSize: const Size(0, 32),
      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );

    final versionItems = <DropdownMenuItem<String?>>[];
    final seen = <String>{};
    for (final s in sets) {
      final v = '${s['version'] ?? s['id'] ?? ''}'.trim();
      if (v.isEmpty || !seen.add(v)) continue;
      final label = '${s['label'] ?? ''}'.trim();
      final isActive = activeVer != null && v == activeVer;
      versionItems.add(
        DropdownMenuItem<String?>(
          value: v,
          child: Text(
            'v$v${label.isNotEmpty ? ' · $label' : ''}'
            '${isActive ? ' · active' : ''}',
            overflow: TextOverflow.ellipsis,
          ),
        ),
      );
    }
    final inList = selectedVer != null && seen.contains(selectedVer);

    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 6, 8, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Wrap(
            spacing: 6,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                state.selectedService == null
                    ? 'Select a service'
                    : state.labelFor(state.selectedService!),
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              SizedBox(
                width: 96,
                child: DropdownButtonFormField<String>(
                  key: ValueKey('ds-env-${state.environment}'),
                  initialValue: state.environment,
                  isDense: true,
                  decoration: const InputDecoration(
                    labelText: 'Env',
                    isDense: true,
                    border: OutlineInputBorder(),
                    contentPadding:
                        EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'dev', child: Text('dev')),
                    DropdownMenuItem(value: 'preprod', child: Text('preprod')),
                    DropdownMenuItem(value: 'prod', child: Text('prod')),
                  ],
                  onChanged: busy
                      ? null
                      : (v) {
                          if (v != null) cubit.setEnvironment(v);
                        },
                ),
              ),
              SizedBox(
                width: 200,
                child: DropdownButtonFormField<String?>(
                  key: ValueKey(
                    'ds-ver-${inList ? selectedVer : 'none'}-${seen.length}-'
                    '${activeVer ?? ''}',
                  ),
                  initialValue: inList ? selectedVer : null,
                  isDense: true,
                  decoration: const InputDecoration(
                    labelText: 'Version',
                    isDense: true,
                    border: OutlineInputBorder(),
                    contentPadding:
                        EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                  ),
                  items: versionItems.isEmpty
                      ? const [
                          DropdownMenuItem<String?>(
                            value: null,
                            enabled: false,
                            child: Text('No versions'),
                          ),
                        ]
                      : versionItems,
                  onChanged: busy ||
                          state.selectedService == null ||
                          versionItems.isEmpty
                      ? null
                      : (v) {
                          if (v != null) cubit.setPayloadVersion(v);
                        },
                ),
              ),
              TextButton(
                style: dense,
                onPressed: state.selectedService == null
                    ? null
                    : cubit.ensurePayloadSet,
                child: const Text('Ensure'),
              ),
              TextButton(
                style: dense,
                onPressed: selectedVer == null || selectedVer.isEmpty
                    ? null
                    : () => cubit.activatePayloadVersion(selectedVer),
                child: const Text('Activate'),
              ),
              TextButton(
                style: dense,
                onPressed: state.generating || state.selectedService == null
                    ? null
                    : cubit.generateAllPayloads,
                child: Text(state.generating ? '…' : 'Generate'),
              ),
              TextButton.icon(
                style: dense,
                onPressed: state.generating || state.selectedService == null
                    ? null
                    : () => pickAndImportPostman(context, cubit, envOnly: false),
                icon: const Icon(Icons.upload_file, size: 16),
                label: const Text('Import'),
              ),
              TextButton.icon(
                style: dense,
                onPressed: state.generating ||
                        state.selectedService == null ||
                        selectedVer == null
                    ? null
                    : () => cubit.downloadPayloadZip(),
                icon: const Icon(Icons.folder_zip_outlined, size: 16),
                label: const Text('Export'),
              ),
              TextButton.icon(
                style: dense,
                onPressed: state.generating || state.selectedService == null
                    ? null
                    : () => pickAndImportPostman(context, cubit, envOnly: true),
                icon: const Icon(Icons.tune, size: 16),
                label: const Text('Import env'),
              ),
              TextButton(
                style: dense,
                onPressed: busy || selectedVer == null
                    ? null
                    : () => _confirmDeleteVersion(context, cubit),
                child: const Text('Delete'),
              ),
              if (summary != null)
                Chip(
                  visualDensity: VisualDensity.compact,
                  label: Text(
                    '${values.length} values · ${rows.length} APIs',
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ),
              if (state.payloadListLoading || state.payloadRowsLoading)
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Expanded(
            child: selectedVer == null
                ? Center(
                    child: Text(
                      state.payloadListLoading
                          ? 'Loading versions…'
                          : sets.isEmpty
                              ? 'No dataset versions. Use Ensure / Generate / Import.'
                              : 'Select a version to load APIs.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  )
                : state.payloadRowsLoading && rows.isEmpty
                    ? const Center(child: CircularProgressIndicator())
                    : rows.isEmpty
                        ? Center(
                            child: Text(
                              state.generating
                                  ? 'Running data prep…'
                                  : 'No rows in this dataset yet. Generate or Import.',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          )
                        : DatasetsRowsList(
                            state: state,
                            cubit: cubit,
                            rows: rows,
                            bySection: bySection,
                          ),
          ),
        ],
      ),
    );
  }
}
