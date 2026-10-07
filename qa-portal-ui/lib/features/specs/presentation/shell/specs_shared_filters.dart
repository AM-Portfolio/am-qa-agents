import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';

/// Env + payload-set version shared across Test / Swagger / MCP / Use cases / Data.
class SpecsSharedFilters extends StatelessWidget {
  const SpecsSharedFilters({
    super.key,
    required this.state,
    required this.cubit,
  });

  final SpecsState state;
  final SpecsCubit cubit;

  @override
  Widget build(BuildContext context) {
    final versions = <String>{
      for (final s in state.payloadSets) '${s['version'] ?? s['id'] ?? ''}',
    }..remove('');
    final sorted = versions.toList()..sort();
    final selectedVer = state.selectedPayloadVersion;
    final apiCount = state.generateResults.isNotEmpty
        ? state.generateResults.length
        : state.apis.length;

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
                contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              ),
              items: const [
                DropdownMenuItem(value: 'dev', child: Text('dev')),
                DropdownMenuItem(value: 'preprod', child: Text('preprod')),
                DropdownMenuItem(value: 'prod', child: Text('prod')),
              ],
              onChanged: state.loading
                  ? null
                  : (v) {
                      if (v != null) cubit.setEnvironment(v);
                    },
            ),
          ),
          SizedBox(
            width: 92,
            child: DropdownButtonFormField<String?>(
              key: ValueKey('shared-ver-$selectedVer'),
              initialValue: selectedVer != null && versions.contains(selectedVer)
                  ? selectedVer
                  : null,
              isDense: true,
              decoration: const InputDecoration(
                labelText: 'data v',
                isDense: true,
                border: OutlineInputBorder(),
                contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              ),
              items: [
                const DropdownMenuItem(value: null, child: Text('(none)')),
                for (final v in sorted)
                  DropdownMenuItem(value: v, child: Text('v$v')),
              ],
              onChanged: state.loading || state.selectedService == null
                  ? null
                  : cubit.setPayloadVersion,
            ),
          ),
          TextButton(
            style: denseBtn,
            onPressed: state.loading || state.selectedService == null
                ? null
                : cubit.ensurePayloadSet,
            child: const Text('Ensure'),
          ),
          TextButton(
            style: denseBtn,
            onPressed: state.loading || selectedVer == null
                ? null
                : () {
                    final v = selectedVer;
                    if (v != null) cubit.activatePayloadVersion(v);
                  },
            child: const Text('Activate'),
          ),
          FilledButton.tonal(
            style: FilledButton.styleFrom(
              visualDensity: VisualDensity.compact,
              padding: const EdgeInsets.symmetric(horizontal: 10),
              minimumSize: const Size(0, 32),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            onPressed: state.generating || state.selectedService == null
                ? null
                : cubit.generateAllPayloads,
            child: Text(
              state.generating ? 'Working…' : 'Generate',
            ),
          ),
          TextButton(
            style: denseBtn,
            onPressed: state.onboarding ||
                    state.loading ||
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
