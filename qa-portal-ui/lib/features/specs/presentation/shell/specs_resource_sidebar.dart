import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';
import 'method_colors.dart';

/// Secondary rail: All APIs + All MCP tools with Flows-like filters.
class SpecsResourceSidebar extends StatefulWidget {
  const SpecsResourceSidebar({
    super.key,
    required this.state,
    required this.cubit,
    this.onSelectApi,
    this.onSelectMcp,
  });

  final SpecsState state;
  final SpecsCubit cubit;
  final VoidCallback? onSelectApi;
  final VoidCallback? onSelectMcp;

  @override
  State<SpecsResourceSidebar> createState() => _SpecsResourceSidebarState();
}

class _SpecsResourceSidebarState extends State<SpecsResourceSidebar> {
  late final TextEditingController _query;

  @override
  void initState() {
    super.initState();
    _query = TextEditingController(text: widget.state.resourceQuery);
  }

  @override
  void didUpdateWidget(covariant SpecsResourceSidebar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.state.resourceQuery != _query.text &&
        widget.state.resourceQuery != oldWidget.state.resourceQuery) {
      _query.text = widget.state.resourceQuery;
    }
  }

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  List<(int, Map<String, dynamic>)> _filteredApis() {
    final q = widget.state.resourceQuery.trim().toLowerCase();
    final out = <(int, Map<String, dynamic>)>[];
    for (var i = 0; i < widget.state.apis.length; i++) {
      final api = widget.state.apis[i];
      final id = SpecsCubit.apiId(api, i).toLowerCase();
      final method = '${api['method'] ?? ''}'.toLowerCase();
      final path = '${api['path'] ?? api['url'] ?? ''}'.toLowerCase();
      final name = '${api['summary'] ?? api['name'] ?? ''}'.toLowerCase();
      if (q.isEmpty ||
          id.contains(q) ||
          method.contains(q) ||
          path.contains(q) ||
          name.contains(q)) {
        out.add((i, api));
      }
    }
    return out;
  }

  List<Map<String, dynamic>> _filteredTools() {
    final q = widget.state.resourceQuery.trim().toLowerCase();
    return widget.state.mcpTools.where((t) {
      final name = '${t['name'] ?? t['tool'] ?? ''}'.toLowerCase();
      final desc = '${t['description'] ?? ''}'.toLowerCase();
      return q.isEmpty || name.contains(q) || desc.contains(q);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final cubit = widget.cubit;
    final cs = Theme.of(context).colorScheme;
    final theme = Theme.of(context);
    final type = state.resourceTypeFilter;
    final showApis = type == 'all' || type == 'apis';
    final showMcp = type == 'all' || type == 'mcp';
    final apis = showApis ? _filteredApis() : const <(int, Map<String, dynamic>)>[];
    final tools = showMcp ? _filteredTools() : const <Map<String, dynamic>>[];

    return GlassCard(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 8, 10, 4),
            child: TextField(
              controller: _query,
              decoration: InputDecoration(
                hintText: 'Filter APIs & MCP…',
                isDense: true,
                filled: true,
                fillColor: cs.surface,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
                prefixIcon: const Icon(Icons.search, size: 18),
                contentPadding: const EdgeInsets.symmetric(vertical: 10),
              ),
              onChanged: cubit.setResourceQuery,
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 0, 10, 6),
            child: Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final entry in const [
                  ('all', 'All'),
                  ('apis', 'APIs'),
                  ('mcp', 'MCP'),
                ])
                  _TypeChip(
                    label: entry.$2,
                    selected: type == entry.$1,
                    onTap: () => cubit.setResourceTypeFilter(entry.$1),
                  ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView(
              children: [
                if (showApis) ...[
                  _SectionHeader(
                    title: 'APIs',
                    count: state.apisLoading ? null : apis.length,
                    loading: state.apisLoading,
                  ),
                  if (state.apisLoading && state.apis.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(16),
                      child: Center(
                        child: SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      ),
                    )
                  else if (apis.isEmpty)
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(
                        'No APIs match.',
                        style: theme.textTheme.bodySmall,
                      ),
                    )
                  else
                    for (final (index, api) in apis)
                      _ApiTile(
                        api: api,
                        index: index,
                        selected:
                            SpecsCubit.apiId(api, index) == state.selectedApiId,
                        checked: state.selectedApiIds
                            .contains(SpecsCubit.apiId(api, index)),
                        onCheck: (v) => cubit.toggleApiSelection(
                          SpecsCubit.apiId(api, index),
                          selected: v,
                        ),
                        onTap: () {
                          cubit.pickApi(api);
                          widget.onSelectApi?.call();
                        },
                      ),
                ],
                if (showMcp) ...[
                  _SectionHeader(
                    title: 'MCP tools',
                    count: state.mcpLoading && state.mcpTools.isEmpty
                        ? null
                        : tools.length,
                    loading: state.mcpLoading,
                  ),
                  if (state.mcpLoading && state.mcpTools.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      child: Column(
                        children: List.generate(
                          3,
                          (_) => Container(
                            height: 36,
                            margin: const EdgeInsets.only(bottom: 6),
                            decoration: BoxDecoration(
                              color: cs.surfaceContainerHighest
                                  .withValues(alpha: 0.4),
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ),
                      ),
                    )
                  else if (tools.isEmpty)
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(
                        'No MCP tools yet.',
                        style: theme.textTheme.bodySmall,
                      ),
                    )
                  else
                    for (final tool in tools)
                      _McpTile(
                        tool: tool,
                        selected: state.selectedMcpToolNames.contains(
                          '${tool['name'] ?? tool['tool'] ?? ''}',
                        ),
                        onTap: () {
                          final name =
                              '${tool['name'] ?? tool['tool'] ?? ''}'.trim();
                          if (name.isNotEmpty) {
                            cubit.toggleMcpToolSelection(name, selected: true);
                          }
                          widget.onSelectMcp?.call();
                        },
                      ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    required this.count,
    required this.loading,
  });

  final String title;
  final int? count;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
      child: Row(
        children: [
          Text(
            title.toUpperCase(),
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  letterSpacing: 0.8,
                  color: cs.onSurfaceVariant,
                  fontWeight: FontWeight.w700,
                ),
          ),
          const Spacer(),
          if (loading)
            const SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(strokeWidth: 1.5),
            )
          else if (count != null)
            Text(
              '$count',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: cs.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                  ),
            ),
        ],
      ),
    );
  }
}

class _TypeChip extends StatelessWidget {
  const _TypeChip({
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

class _ApiTile extends StatelessWidget {
  const _ApiTile({
    required this.api,
    required this.index,
    required this.selected,
    required this.checked,
    required this.onCheck,
    required this.onTap,
  });

  final Map<String, dynamic> api;
  final int index;
  final bool selected;
  final bool checked;
  final ValueChanged<bool> onCheck;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final method = '${api['method'] ?? ''}'.toUpperCase();
    final path = '${api['path'] ?? api['url'] ?? ''}';
    return ListTile(
      dense: true,
      selected: selected,
      selectedTileColor: AppColors.primary.withValues(alpha: 0.1),
      leading: Checkbox(
        value: checked,
        onChanged: (v) => onCheck(v == true),
      ),
      title: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
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
      onTap: onTap,
    );
  }
}

class _McpTile extends StatelessWidget {
  const _McpTile({
    required this.tool,
    required this.selected,
    required this.onTap,
  });

  final Map<String, dynamic> tool;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final name = '${tool['name'] ?? tool['tool'] ?? ''}';
    final desc = '${tool['description'] ?? ''}';
    return ListTile(
      dense: true,
      selected: selected,
      selectedTileColor: AppColors.primary.withValues(alpha: 0.1),
      leading: Icon(
        Icons.smart_toy_outlined,
        size: 18,
        color: selected
            ? Theme.of(context).colorScheme.primary
            : Theme.of(context).colorScheme.onSurfaceVariant,
      ),
      title: Text(name, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: desc.isEmpty
          ? null
          : Text(
              desc,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelSmall,
            ),
      onTap: onTap,
    );
  }
}
