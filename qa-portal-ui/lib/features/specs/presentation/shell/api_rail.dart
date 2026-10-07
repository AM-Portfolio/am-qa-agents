import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';
import 'method_colors.dart';

/// Middle rail: visible API checklist + one-click Test.
/// Payload-set version / Ensure / Activate live on the Data tab.
class SpecsApiRail extends StatelessWidget {
  const SpecsApiRail({
    super.key,
    required this.state,
    required this.cubit,
    required this.apis,
    required this.onFilterChanged,
  });

  final SpecsState state;
  final SpecsCubit cubit;
  final List<(int, Map<String, dynamic>)> apis;
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
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'APIs (${apis.length})',
                        style: Theme.of(context).textTheme.labelLarge,
                      ),
                    ),
                    TextButton(
                      onPressed: cubit.selectAllApis,
                      child: const Text('All'),
                    ),
                    TextButton(
                      onPressed: cubit.clearApiSelection,
                      child: const Text('Clear'),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                TextField(
                  decoration: const InputDecoration(
                    hintText: 'Filter APIs',
                    isDense: true,
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.filter_list, size: 16),
                  ),
                  onChanged: onFilterChanged,
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(
                      '${state.selectedApiIds.length}/${state.apis.length}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const Spacer(),
                    TextButton(
                      onPressed: state.loading || state.selectedApiIds.isEmpty
                          ? null
                          : cubit.testCheckedApis,
                      child: const Text('Test ✓'),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView.separated(
              itemCount: apis.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (_, i) {
                final (index, api) = apis[i];
                final id = SpecsCubit.apiId(api, index);
                final method = '${api['method'] ?? ''}'.toUpperCase();
                final path = '${api['path'] ?? api['url'] ?? ''}';
                final checked = state.selectedApiIds.contains(id);
                return ListTile(
                  dense: true,
                  selected: id == state.selectedApiId,
                  selectedTileColor: AppColors.primary.withValues(alpha: 0.1),
                  leading: Checkbox(
                    value: checked,
                    onChanged: (v) => cubit.toggleApiSelection(
                      id,
                      selected: v == true,
                    ),
                  ),
                  title: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 5,
                          vertical: 1,
                        ),
                        decoration: BoxDecoration(
                          color: methodBg(method),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          method,
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: methodFg(method),
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          path,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                  trailing: IconButton(
                    tooltip: 'Test (load set v + Send)',
                    icon: const Icon(Icons.play_arrow, size: 18),
                    onPressed: state.loading
                        ? null
                        : () => cubit.testApiOneClick(api),
                  ),
                  onTap: () => cubit.pickApi(api),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
