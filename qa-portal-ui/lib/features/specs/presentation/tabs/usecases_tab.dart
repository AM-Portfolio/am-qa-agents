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

    if (state.overviewLoading && state.overview == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.selectedService == null) {
      return const Center(child: Text('Select a service in the workspace.'));
    }
    if (useCases.isEmpty && skills.isEmpty) {
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

