import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../data/runs_repository.dart';
import '../cubit/runs_cubit.dart';

class RunsPage extends StatelessWidget {
  const RunsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => RunsCubit(getIt<RunsRepository>())..load(),
      child: const _RunsView(),
    );
  }
}

class _RunsView extends StatelessWidget {
  const _RunsView();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Text('Runs', style: Theme.of(context).textTheme.headlineSmall),
              const Spacer(),
              FilledButton.icon(
                onPressed: () => context.read<RunsCubit>().load(),
                icon: const Icon(Icons.refresh, size: 18),
                label: const Text('Refresh'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Expanded(
            child: BlocBuilder<RunsCubit, RunsState>(
              builder: (context, state) {
                if (state.loading && state.items.isEmpty) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (state.error != null && state.items.isEmpty) {
                  return Center(
                    child: Text(
                      state.error!,
                      style: TextStyle(color: Theme.of(context).colorScheme.error),
                    ),
                  );
                }
                if (state.items.isEmpty) {
                  return Center(
                    child: Text(
                      'No runs yet. Use Execute above to start a test.',
                      style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                            color: AppColors.textSecondaryLight,
                          ),
                    ),
                  );
                }
                return ListView.separated(
                  itemCount: state.items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final r = state.items[i];
                    final id = '${r['id'] ?? ''}';
                    final status = '${r['status'] ?? ''}';
                    final name = '${r['config_name'] ?? r['name'] ?? id}';
                    final testType = '${r['test_type'] ?? ''}';
                    return ListTile(
                      title: Text(name),
                      subtitle: Text('$status · $testType · $id'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: id.isEmpty ? null : () => context.go('/runs/$id'),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
