import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/flows_cubit.dart';
import '../cubit/flows_state.dart';
import '../utils/flows_display.dart';

class FlowsToolbar extends StatelessWidget {
  const FlowsToolbar({
    required this.state,
    required this.onSchedule,
    required this.onSuite,
    required this.onSaveGraph,
  });

  final FlowsState state;
  final VoidCallback onSchedule;
  final VoidCallback onSuite;
  final VoidCallback onSaveGraph;

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<FlowsCubit>();
    final rt = state.runtime;
    final sets = (rt?['payload_sets'] is List)
        ? List<Map<String, dynamic>>.from(
            (rt!['payload_sets'] as List).whereType<Map>().map(
                  (e) => Map<String, dynamic>.from(e),
                ),
          )
        : <Map<String, dynamic>>[];
    final active = rt?['active_version'];
    final selectedRaw = rt?['selected_version'] ?? active;
    final selectedVer = selectedRaw is int
        ? selectedRaw
        : int.tryParse('$selectedRaw');
    final datasetMissing = sets.isNotEmpty && selectedVer == null;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Wrap(
        spacing: 12,
        runSpacing: 8,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Text(
            state.isDraft
                ? 'Untitled (draft)'
                : (state.selectedFlowId ?? '—'),
            style: Theme.of(context).textTheme.titleSmall,
          ),
          DropdownButton<String>(
            value: state.env,
            items: const [
              DropdownMenuItem(value: 'prod', child: Text('prod')),
              DropdownMenuItem(value: 'preprod', child: Text('preprod')),
              DropdownMenuItem(value: 'dev', child: Text('dev')),
            ],
            onChanged: (v) {
              if (v != null) cubit.setEnv(v);
            },
          ),
          DropdownButton<String?>(
            value: state.credentials.any((c) => '${c['id']}' == state.credentialId)
                ? state.credentialId
                : null,
            hint: const Text('Credential'),
            items: [
              const DropdownMenuItem<String?>(
                value: null,
                child: Text('SPT env default'),
              ),
              ...state.credentials.map(
                (c) => DropdownMenuItem<String?>(
                  value: '${c['id']}',
                  child: Text('${c['name']} (${c['env']})'),
                ),
              ),
            ],
            onChanged: cubit.setCredentialId,
          ),
          if (sets.isNotEmpty)
            Tooltip(
              message: datasetMissing
                  ? 'Required: pick Default / Full / Premium dataset'
                  : 'Specs payload-set version used for request bodies',
              child: DropdownButton<int>(
                value: sets.any((s) =>
                        int.tryParse('${s['version']}') == selectedVer)
                    ? selectedVer
                    : null,
                hint: Text(
                  datasetMissing ? 'Dataset required' : 'Dataset',
                  style: TextStyle(
                    color: datasetMissing
                        ? Theme.of(context).colorScheme.error
                        : null,
                  ),
                ),
                items: [
                  for (final s in sets)
                    if (int.tryParse('${s['version']}') != null)
                      DropdownMenuItem(
                        value: int.parse('${s['version']}'),
                        child: Text(
                          payloadSetMenuLabel(s, active: active),
                        ),
                      ),
                ],
                onChanged: state.isDraft || state.selectedFlowId == null
                    ? null
                    : (v) {
                        if (v == null) return;
                        cubit.activatePayloadVersion(v, pin: true);
                      },
              ),
            ),
          FilledButton.icon(
            onPressed: state.executing ||
                    state.isDraft ||
                    state.selectedFlowId == null
                ? null
                : () => cubit.runSelected(),
            icon: state.executing
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.play_arrow, size: 18),
            label: Text(state.executing ? 'Running…' : 'Run'),
          ),
          OutlinedButton.icon(
            onPressed: (state.graphDirty || state.isDraft) &&
                    state.graph != null &&
                    state.graph!.isNotEmpty
                ? onSaveGraph
                : null,
            icon: const Icon(Icons.save_outlined, size: 18),
            label: Text(
              state.isDraft
                  ? 'Save flow…'
                  : (state.graphDirty ? 'Save graph*' : 'Save graph'),
            ),
          ),
          OutlinedButton.icon(
            onPressed: onSuite,
            icon: const Icon(Icons.playlist_play, size: 18),
            label: const Text('Run suite…'),
          ),
          OutlinedButton.icon(
            onPressed: state.isDraft || state.selectedFlowId == null
                ? null
                : onSchedule,
            icon: const Icon(Icons.schedule, size: 18),
            label: const Text('Schedule'),
          ),
          if (state.executing)
            TextButton(
              onPressed: () => cubit.stop(),
              child: const Text('Stop'),
            ),
        ],
      ),
    );
  }
}

