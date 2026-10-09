import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/network/json_lists.dart';
import '../../../../core/router/app_router.dart';
import '../../../services/presentation/widgets/coverage_board.dart';
import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';

class SpecsUseCasesTab extends StatelessWidget {
  const SpecsUseCasesTab({required this.state});

  final SpecsState state;

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<SpecsCubit>();
    final ov = state.overview ?? const <String, dynamic>{};
    final skills = mapList(ov['skills']);
    final features = mapList(ov['features']);
    final useCases = mapList(ov['use_cases']).isNotEmpty
        ? mapList(ov['use_cases'])
        : features;
    final payloads = ov['payloads'] is Map
        ? Map<String, dynamic>.from(ov['payloads'] as Map)
        : const <String, dynamic>{};
    final dataGenFlows = mapList(ov['data_gen_flows']);

    if (state.overviewLoading && state.overview == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.selectedService == null) {
      return const Center(child: Text('Select a service in the workspace.'));
    }
    if (useCases.isEmpty &&
        skills.isEmpty &&
        dataGenFlows.isEmpty &&
        (payloads['api_count'] ?? 0) == 0) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'No use cases yet for ${state.selectedService}.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: cubit.loadOverview,
              child: const Text('Refresh'),
            ),
          ],
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(8),
      children: [
        _DataGenPanel(
          serviceId: state.selectedService ?? '',
          payloads: payloads,
          dataGenFlows: dataGenFlows,
          onOpenFlows: () => context.go(AppRoutes.flows),
        ),
        CoverageBoard(
          skills: skills,
          useCases: useCases,
          serviceId: state.selectedService ?? '',
          environment: state.environment,
          onRun: () async {
            final runId = await cubit.runUseCases();
            if (!context.mounted) return;
            if (runId != null && runId.isNotEmpty) {
              context.go('${AppRoutes.runs}/$runId');
            } else {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(
                    state.message ??
                        'Could not start run for this service.',
                  ),
                  behavior: SnackBarBehavior.floating,
                ),
              );
            }
          },
        ),
      ],
    );
  }
}

class _DataGenPanel extends StatelessWidget {
  const _DataGenPanel({
    required this.serviceId,
    required this.payloads,
    required this.dataGenFlows,
    required this.onOpenFlows,
  });

  final String serviceId;
  final Map<String, dynamic> payloads;
  final List<Map<String, dynamic>> dataGenFlows;
  final VoidCallback onOpenFlows;

  @override
  Widget build(BuildContext context) {
    final apiCount = payloads['api_count'] ?? 0;
    final active = payloads['active_version'];
    final sets = mapList(payloads['sets']);
    if (apiCount == 0 && dataGenFlows.isEmpty && sets.isEmpty) {
      return const SizedBox.shrink();
    }
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Data gen · $serviceId',
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  TextButton.icon(
                    onPressed: onOpenFlows,
                    icon: const Icon(Icons.account_tree_outlined, size: 16),
                    label: const Text('Open Flows'),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                active == null
                    ? 'No active payload set'
                    : 'Active payload set v$active · $apiCount API rows'
                        '${payloads['active_label'] != null ? ' · ${payloads['active_label']}' : ''}',
                style: theme.textTheme.bodySmall,
              ),
              if (sets.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text('Payload sets', style: theme.textTheme.labelLarge),
                const SizedBox(height: 4),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final s in sets.take(8))
                      Chip(
                        label: Text(
                          'v${s['version'] ?? '?'}'
                          '${s['label'] != null ? ' · ${s['label']}' : ''}',
                          style: const TextStyle(fontSize: 11),
                        ),
                        visualDensity: VisualDensity.compact,
                      ),
                  ],
                ),
              ],
              if (dataGenFlows.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  'Cross flows (${dataGenFlows.length})',
                  style: theme.textTheme.labelLarge,
                ),
                const SizedBox(height: 4),
                for (final f in dataGenFlows.take(12))
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: Text(
                      '${f['title'] ?? f['id']}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text(
                      '${f['id']} · ${f['node_count'] ?? 0} nodes · ${f['category'] ?? ''}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.labelSmall,
                    ),
                    trailing: const Icon(Icons.chevron_right, size: 18),
                    onTap: onOpenFlows,
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
