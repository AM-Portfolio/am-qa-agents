import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';

/// Filterable collection (service) list — Flows-like search + runtime + facet chips.
class SpecsCollectionsSidebar extends StatefulWidget {
  const SpecsCollectionsSidebar({
    super.key,
    required this.state,
    required this.cubit,
    this.showAsSwitcher = false,
  });

  final SpecsState state;
  final SpecsCubit cubit;
  /// Compact header when a collection is already selected (switcher).
  final bool showAsSwitcher;

  @override
  State<SpecsCollectionsSidebar> createState() =>
      _SpecsCollectionsSidebarState();
}

class _SpecsCollectionsSidebarState extends State<SpecsCollectionsSidebar> {
  late final TextEditingController _query;

  @override
  void initState() {
    super.initState();
    _query = TextEditingController(text: widget.state.collectionQuery);
  }

  @override
  void didUpdateWidget(covariant SpecsCollectionsSidebar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.state.collectionQuery != _query.text &&
        widget.state.collectionQuery != oldWidget.state.collectionQuery) {
      _query.text = widget.state.collectionQuery;
    }
  }

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  List<String> _filtered() {
    final q = widget.state.collectionQuery.trim().toLowerCase();
    final runtime = widget.state.collectionRuntimeFilter.trim().toLowerCase();
    final facet = widget.state.collectionFacet.trim().toLowerCase();
    return widget.state.services.where((id) {
      final label = widget.state.labelFor(id).toLowerCase();
      if (q.isNotEmpty &&
          !id.toLowerCase().contains(q) &&
          !label.contains(q)) {
        return false;
      }
      if (runtime.isNotEmpty && !id.toLowerCase().contains(runtime)) {
        return false;
      }
      if (facet.isNotEmpty &&
          !id.toLowerCase().contains(facet) &&
          !label.contains(facet)) {
        return false;
      }
      return true;
    }).toList();
  }

  String _pretty(String id) {
    final cleaned = id
        .replaceFirst(RegExp(r'^am[-_]'), '')
        .replaceAll(RegExp(r'[-_]+'), ' ')
        .trim();
    if (cleaned.isEmpty) return id;
    return cleaned
        .split(' ')
        .where((w) => w.isNotEmpty)
        .map((w) => '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final cubit = widget.cubit;
    final cs = Theme.of(context).colorScheme;
    final theme = Theme.of(context);
    final services = _filtered();
    final runtimes = <String>{
      for (final id in state.services)
        if (id.contains('-')) id.split('-').first else id,
    }.toList()
      ..sort();

    if (widget.showAsSwitcher && state.selectedService != null) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(10, 8, 10, 4),
        child: MenuAnchor(
          builder: (context, controller, _) {
            return Material(
              color: cs.surface,
              borderRadius: BorderRadius.circular(10),
              child: InkWell(
                borderRadius: BorderRadius.circular(10),
                onTap: () {
                  if (controller.isOpen) {
                    controller.close();
                  } else {
                    controller.open();
                  }
                },
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: cs.outlineVariant),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.folder_outlined, size: 18, color: cs.primary),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          state.labelFor(state.selectedService!),
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      Icon(
                        controller.isOpen
                            ? Icons.expand_less
                            : Icons.expand_more,
                        size: 18,
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
          menuChildren: [
            for (final id in state.services)
              MenuItemButton(
                onPressed: () => cubit.selectService(id),
                child: Text(state.labelFor(id)),
              ),
          ],
        ),
      );
    }

    return GlassCard(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 6),
            child: Text(
              'Collections (${services.length})',
              style: theme.textTheme.labelLarge,
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
            child: TextField(
              controller: _query,
              decoration: InputDecoration(
                hintText: 'Filter collections…',
                isDense: true,
                filled: true,
                fillColor: cs.surface,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
                prefixIcon: const Icon(Icons.search, size: 18),
                contentPadding: const EdgeInsets.symmetric(vertical: 10),
              ),
              onChanged: cubit.setCollectionQuery,
            ),
          ),
          if (runtimes.length > 1)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
              child: MenuAnchor(
                builder: (context, controller, _) {
                  final label = state.collectionRuntimeFilter.isEmpty
                      ? 'All runtimes'
                      : state.collectionRuntimeFilter;
                  return Material(
                    color: cs.surface,
                    borderRadius: BorderRadius.circular(10),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(10),
                      onTap: () {
                        if (controller.isOpen) {
                          controller.close();
                        } else {
                          controller.open();
                        }
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 10,
                        ),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: cs.outlineVariant),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.dns_outlined, size: 18, color: cs.primary),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                label,
                                style: theme.textTheme.titleSmall?.copyWith(
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                            Icon(
                              controller.isOpen
                                  ? Icons.expand_less
                                  : Icons.expand_more,
                              size: 18,
                            ),
                          ],
                        ),
                      ),
                    ),
                  );
                },
                menuChildren: [
                  MenuItemButton(
                    onPressed: () => cubit.setCollectionRuntimeFilter(''),
                    child: const Text('All runtimes'),
                  ),
                  for (final r in runtimes)
                    MenuItemButton(
                      onPressed: () => cubit.setCollectionRuntimeFilter(r),
                      child: Text(r),
                    ),
                ],
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 4),
            child: Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                _SpecChip(
                  label: 'All',
                  selected: state.collectionFacet.isEmpty,
                  onTap: () => cubit.setCollectionFacet(''),
                ),
                _SpecChip(
                  label: 'am-',
                  selected: state.collectionFacet == 'am-',
                  onTap: () => cubit.setCollectionFacet(
                    state.collectionFacet == 'am-' ? '' : 'am-',
                  ),
                ),
                _SpecChip(
                  label: 'agent',
                  selected: state.collectionFacet == 'agent',
                  onTap: () => cubit.setCollectionFacet(
                    state.collectionFacet == 'agent' ? '' : 'agent',
                  ),
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
                final selected = id == state.selectedService;
                return ListTile(
                  dense: true,
                  selected: selected,
                  selectedTileColor: AppColors.primary.withValues(alpha: 0.14),
                  leading: Icon(
                    Icons.folder_outlined,
                    size: 18,
                    color: selected ? cs.primary : cs.onSurfaceVariant,
                  ),
                  title: Text(_pretty(id), maxLines: 1),
                  subtitle: Text(
                    id,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.labelSmall,
                  ),
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

class _SpecChip extends StatelessWidget {
  const _SpecChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Material(
      color: selected ? cs.primary : cs.surface,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: selected ? cs.primary : cs.outlineVariant,
            ),
          ),
          child: Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: selected ? cs.onPrimary : cs.onSurface,
                  fontWeight: FontWeight.w600,
                ),
          ),
        ),
      ),
    );
  }
}
