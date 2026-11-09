import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';

/// Left rail: workspace services (env lives in shared filters above tabs).
class SpecsCatalogRail extends StatelessWidget {
  const SpecsCatalogRail({
    super.key,
    required this.state,
    required this.cubit,
    required this.services,
    required this.onFilterChanged,
  });

  final SpecsState state;
  final SpecsCubit cubit;
  final List<String> services;
  final ValueChanged<String> onFilterChanged;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: EdgeInsets.zero,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 8, 8, 4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Workspace (${services.length})',
                  style: Theme.of(context).textTheme.labelLarge,
                ),
                const SizedBox(height: 6),
                TextField(
                  decoration: const InputDecoration(
                    hintText: 'Filter services',
                    isDense: true,
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.search, size: 16),
                  ),
                  onChanged: onFilterChanged,
                ),
                Text(
                  'health: ${state.health?['status'] ?? '?'} · ${state.environment}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView.builder(
              itemCount: services.length,
              itemBuilder: (_, i) {
                final id = services[i];
                return ListTile(
                  dense: true,
                  selected: id == state.selectedService,
                  selectedTileColor: AppColors.primary.withValues(alpha: 0.14),
                  title: Text(state.labelFor(id), maxLines: 1),
                  onTap: () => cubit.selectService(id),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
