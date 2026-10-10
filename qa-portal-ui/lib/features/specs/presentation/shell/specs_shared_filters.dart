import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';

/// Env + dataset version + onboard controls for the OpenAPI workspace.
class SpecsSharedFilters extends StatelessWidget {
  const SpecsSharedFilters({
    super.key,
    required this.state,
    required this.cubit,
    this.onOpenDatasets,
  });

  final SpecsState state;
  final SpecsCubit cubit;
  final VoidCallback? onOpenDatasets;

  @override
  Widget build(BuildContext context) {
    final selectedVer = state.selectedPayloadVersion;
    final apiCount = state.apis.length;
    final busy = state.apisLoading || state.payloadListLoading;
    final sets = state.payloadSets;

    final denseBtn = TextButton.styleFrom(
      visualDensity: VisualDensity.compact,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      minimumSize: const Size(0, 32),
      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
    return Padding(
      padding: const EdgeInsets.fromLTRB(6, 4, 6, 4),
      child: Wrap(
        spacing: 4,
        runSpacing: 4,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Text(
            selectedVer != null ? 'Config · data v$selectedVer' : 'Config',
            style: Theme.of(context).textTheme.labelLarge,
          ),
          if (apiCount > 0)
            Chip(
              visualDensity: VisualDensity.compact,
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              label: Text(
                '$apiCount APIs',
                style: Theme.of(context).textTheme.labelSmall,
              ),
              padding: EdgeInsets.zero,
              labelPadding: const EdgeInsets.symmetric(horizontal: 6),
            ),
          ActionChip(
            visualDensity: VisualDensity.compact,
            avatar: const Icon(Icons.storage_outlined, size: 16),
            label: Text(
              selectedVer != null ? 'Datasets v$selectedVer' : 'Datasets',
              style: Theme.of(context).textTheme.labelSmall,
            ),
            onPressed: onOpenDatasets,
          ),
          SizedBox(
            width: 88,
            child: DropdownButtonFormField<String>(
              key: ValueKey('shared-env-${state.environment}'),
              initialValue: state.environment,
              isDense: true,
              decoration: const InputDecoration(
                labelText: 'env',
                isDense: true,
                border: OutlineInputBorder(),
                contentPadding:
                    EdgeInsets.symmetric(horizontal: 6, vertical: 4),
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
          Builder(
            builder: (context) {
              final versionItems = <DropdownMenuItem<String?>>[
                const DropdownMenuItem<String?>(
                  value: null,
                  child: Text('active / none'),
                ),
              ];
              final seen = <String>{};
              for (final s in sets) {
                final v = '${s['version'] ?? s['id'] ?? ''}'.trim();
                if (v.isEmpty || !seen.add(v)) continue;
                final active =
                    s['active'] == true || s['is_active'] == true;
                versionItems.add(
                  DropdownMenuItem<String?>(
                    value: v,
                    child: Text(
                      'v$v${active ? ' · active' : ''}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                );
              }
              final inList =
                  selectedVer != null && seen.contains(selectedVer);
              return SizedBox(
                width: 148,
                child: DropdownButtonFormField<String?>(
                  key: ValueKey(
                    'shared-dataset-${inList ? selectedVer : 'none'}-'
                    '${seen.length}',
                  ),
                  initialValue: inList ? selectedVer : null,
                  isDense: true,
                  decoration: const InputDecoration(
                    labelText: 'Dataset',
                    isDense: true,
                    border: OutlineInputBorder(),
                    contentPadding:
                        EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                  ),
                  items: versionItems,
                  onChanged: busy || state.selectedService == null
                      ? null
                      : (v) => cubit.setPayloadVersion(v),
                ),
              );
            },
          ),
          TextButton(
            style: denseBtn,
            onPressed: state.onboarding ||
                    busy ||
                    state.selectedService == null
                ? null
                : cubit.startOnboardPrep,
            child: Text(state.onboarding ? 'Onboard…' : 'Onboard prep'),
          ),
          if (state.onboardReport != null)
            Chip(
              visualDensity: VisualDensity.compact,
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              label: Text(
                state.onboardReport!['ok'] == true
                    ? 'onboard ok'
                    : 'fail:${state.onboardReport!['failed_step'] ?? '?'}',
                style: Theme.of(context).textTheme.labelSmall,
              ),
              padding: EdgeInsets.zero,
              labelPadding: const EdgeInsets.symmetric(horizontal: 6),
            ),
        ],
      ),
    );
  }
}
