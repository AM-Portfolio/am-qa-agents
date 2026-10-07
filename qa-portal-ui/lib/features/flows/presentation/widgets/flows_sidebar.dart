import 'package:flutter/material.dart';

class FlowsSidebar extends StatelessWidget {
  const FlowsSidebar({
    required this.flows,
    required this.onSelect,
    this.selectedFlowId,
  });

  final List<Map<String, dynamic>> flows;
  final String? selectedFlowId;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    final byGroup = <String, Map<String, List<Map<String, dynamic>>>>{};
    for (final f in flows) {
      final g = '${f['group'] ?? 'other'}';
      final c = '${f['category'] ?? 'general'}';
      byGroup.putIfAbsent(g, () => {});
      byGroup[g]!.putIfAbsent(c, () => []).add(f);
    }
    final groups = byGroup.keys.toList()..sort();
    return ListView(
      children: [
        for (final g in groups) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Text(
              g.toUpperCase(),
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ),
          for (final cat in (byGroup[g]!.keys.toList()..sort())) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 6, 12, 2),
              child: Text(
                cat,
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: Theme.of(context).colorScheme.primary,
                    ),
              ),
            ),
            for (final f in byGroup[g]![cat]!)
              Builder(
                builder: (context) {
                  final id = '${f['id']}';
                  final selected = id == selectedFlowId;
                  return ListTile(
                    dense: true,
                    contentPadding: const EdgeInsets.only(left: 28, right: 12),
                    selected: selected,
                    title: Text(
                      '${f['title'] ?? id}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text(
                      '$id · ${f['source'] ?? ''} · ${f['node_count'] ?? 0}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    onTap: () => onSelect(id),
                  );
                },
              ),
          ],
        ],
      ],
    );
  }
}

