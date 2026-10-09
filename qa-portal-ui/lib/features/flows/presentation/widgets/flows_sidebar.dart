import 'package:flutter/material.dart';

/// Compact service-first flows rail: search → service → category chips → flat list.
class FlowsSidebar extends StatefulWidget {
  const FlowsSidebar({
    super.key,
    required this.flows,
    required this.onSelect,
    this.selectedFlowId,
    this.flowQuery = '',
    this.categoryFilter = '',
    this.apiPackFilter = '',
    this.facets,
    this.catalogServices = const [],
    this.flowsTotal = 0,
    this.loadingMore = false,
    this.hasMore = false,
    this.onQueryChanged,
    this.onCategoryFilter,
    this.onApiPackFilter,
    this.onLoadMore,
    this.onLoadAll,
  });

  final List<Map<String, dynamic>> flows;
  final String? selectedFlowId;
  final String flowQuery;
  final String categoryFilter;
  final String apiPackFilter;
  final Map<String, dynamic>? facets;
  final List<String> catalogServices;
  final int flowsTotal;
  final bool loadingMore;
  final bool hasMore;
  final ValueChanged<String>? onQueryChanged;
  final ValueChanged<String>? onCategoryFilter;
  final ValueChanged<String>? onApiPackFilter;
  final VoidCallback? onLoadMore;
  final VoidCallback? onLoadAll;
  final ValueChanged<String> onSelect;

  @override
  State<FlowsSidebar> createState() => _FlowsSidebarState();
}

class _FlowsSidebarState extends State<FlowsSidebar> {
  late final TextEditingController _query;

  @override
  void initState() {
    super.initState();
    _query = TextEditingController(text: widget.flowQuery);
  }

  @override
  void didUpdateWidget(covariant FlowsSidebar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.flowQuery != _query.text &&
        widget.flowQuery != oldWidget.flowQuery) {
      _query.text = widget.flowQuery;
    }
  }

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  List<_Facet> _facetList(String key) {
    final raw = widget.facets?[key];
    if (raw is! List) return const [];
    final out = <_Facet>[];
    for (final e in raw) {
      if (e is! Map) continue;
      final id = '${e['id'] ?? ''}'.trim();
      if (id.isEmpty) continue;
      final c = e['count'];
      out.add(_Facet(id, c is int ? c : int.tryParse('$c') ?? 0));
    }
    out.sort((a, b) => a.id.compareTo(b.id));
    return out;
  }

  String _prettyService(String id) {
    if (id.isEmpty) return 'All services';
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

  Color _statusColor(Map<String, dynamic> f, ColorScheme cs) {
    final tags = f['tags'];
    final gate = '${f['gate'] ?? ''}'.toLowerCase();
    if (tags is List && tags.any((t) => '$t'.toLowerCase().contains('negative'))) {
      return cs.error;
    }
    if (gate.contains('prod')) return const Color(0xFF3DDC97);
    return cs.tertiary;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final serviceFacets = _facetList('services');
    final categoryFacets = _facetList('categories');

    final serviceIds = <String>{
      for (final s in serviceFacets) s.id,
      ...widget.catalogServices.map((e) => e.trim()).where((e) => e.isNotEmpty),
    }.toList()
      ..sort();

    final selectedService = widget.apiPackFilter;
    final serviceLabel = selectedService.isEmpty
        ? 'All services'
        : _prettyService(selectedService);
    int? countFor(String id) {
      for (final s in serviceFacets) {
        if (s.id == id) return s.count;
      }
      return null;
    }

    final serviceCount = selectedService.isEmpty
        ? widget.flowsTotal
        : (countFor(selectedService) ?? widget.flowsTotal);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
          child: TextField(
            controller: _query,
            decoration: InputDecoration(
              hintText: 'Filter workflows…',
              isDense: true,
              filled: true,
              fillColor: cs.surface,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: BorderSide(color: cs.outlineVariant),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: BorderSide(color: cs.outlineVariant),
              ),
              prefixIcon: const Icon(Icons.search, size: 18),
              contentPadding: const EdgeInsets.symmetric(vertical: 10),
            ),
            onChanged: widget.onQueryChanged,
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
          child: MenuAnchor(
            alignmentOffset: const Offset(0, 4),
            style: MenuStyle(
              maximumSize: WidgetStatePropertyAll(
                Size(MediaQuery.sizeOf(context).width, 320),
              ),
              padding: const WidgetStatePropertyAll(EdgeInsets.zero),
              shape: WidgetStatePropertyAll(
                RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                  side: BorderSide(color: cs.outlineVariant),
                ),
              ),
            ),
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
                        Icon(Icons.domain_outlined,
                            size: 18, color: cs.primary),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            serviceLabel,
                            style: theme.textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color:
                                cs.primaryContainer.withValues(alpha: 0.55),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            '$serviceCount flows',
                            style: theme.textTheme.labelSmall?.copyWith(
                              color: cs.onPrimaryContainer,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        const SizedBox(width: 4),
                        Icon(
                          controller.isOpen
                              ? Icons.expand_less
                              : Icons.expand_more,
                          size: 18,
                          color: cs.onSurfaceVariant,
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
            menuChildren: [
              SizedBox(
                width: 296,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    MenuItemButton(
                      leadingIcon: Icon(
                        Icons.apps_outlined,
                        color: selectedService.isEmpty ? cs.primary : null,
                      ),
                      trailingIcon: selectedService.isEmpty
                          ? Icon(Icons.check, size: 18, color: cs.primary)
                          : null,
                      onPressed: () => widget.onApiPackFilter?.call(''),
                      child: const Text('All services'),
                    ),
                    const Divider(height: 1),
                    ConstrainedBox(
                      constraints: const BoxConstraints(maxHeight: 260),
                      child: SingleChildScrollView(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            for (final id in serviceIds)
                              MenuItemButton(
                                leadingIcon:
                                    const Icon(Icons.domain_outlined),
                                trailingIcon: selectedService == id
                                    ? Icon(Icons.check,
                                        size: 18, color: cs.primary)
                                    : (countFor(id) != null
                                        ? Text(
                                            '${countFor(id)}',
                                            style: theme.textTheme.labelSmall,
                                          )
                                        : null),
                                onPressed: () =>
                                    widget.onApiPackFilter?.call(id),
                                child: Column(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.start,
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Text(_prettyService(id)),
                                    Text(
                                      id,
                                      style: theme.textTheme.bodySmall
                                          ?.copyWith(
                                        color: cs.onSurfaceVariant,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (categoryFacets.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 4),
            child: Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                _CatChip(
                  label: 'All',
                  selected: widget.categoryFilter.isEmpty,
                  onTap: () => widget.onCategoryFilter?.call(''),
                ),
                for (final c in categoryFacets)
                  _CatChip(
                    label: _prettyService(c.id),
                    selected: widget.categoryFilter == c.id,
                    onTap: () {
                      final next =
                          widget.categoryFilter == c.id ? '' : c.id;
                      widget.onCategoryFilter?.call(next);
                    },
                  ),
              ],
            ),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
          child: Row(
            children: [
              Text(
                'WORKFLOWS',
                style: theme.textTheme.labelSmall?.copyWith(
                  letterSpacing: 0.8,
                  color: cs.onSurfaceVariant,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const Spacer(),
              Text(
                '${widget.flows.length}${widget.flowsTotal > widget.flows.length ? ' / ${widget.flowsTotal}' : ''} loaded',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: cs.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: widget.flows.isEmpty
              ? Center(
                  child: Text(
                    'No workflows match',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: cs.onSurfaceVariant,
                    ),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
                  itemCount: widget.flows.length + (widget.hasMore ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index >= widget.flows.length) {
                      return Padding(
                        padding: const EdgeInsets.fromLTRB(8, 8, 8, 4),
                        child: widget.loadingMore
                            ? const Center(
                                child: Padding(
                                  padding: EdgeInsets.all(12),
                                  child: SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  ),
                                ),
                              )
                            : Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  FilledButton.tonal(
                                    onPressed: widget.onLoadAll,
                                    child: Text(
                                      'Load all (${widget.flowsTotal - widget.flows.length} more)',
                                    ),
                                  ),
                                  TextButton(
                                    onPressed: widget.onLoadMore,
                                    child: const Text('Load more'),
                                  ),
                                ],
                              ),
                      );
                    }
                    final f = widget.flows[index];
                    final id = '${f['id']}';
                    final selected = id == widget.selectedFlowId;
                    final title = '${f['title'] ?? id}';
                    final cat = '${f['category'] ?? ''}'.trim();
                    final source = '${f['source'] ?? ''}'.trim();
                    final nodes = f['node_count'] ?? 0;
                    final subtitle = [
                      if (cat.isNotEmpty) cat,
                      if (source.isNotEmpty) source,
                      '$nodes step${nodes == 1 ? '' : 's'}',
                    ].join(' · ');

                    return Padding(
                      padding: const EdgeInsets.only(bottom: 2),
                      child: Material(
                        color: selected
                            ? cs.primaryContainer.withValues(alpha: 0.45)
                            : Colors.transparent,
                        borderRadius: BorderRadius.circular(10),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(10),
                          onTap: () => widget.onSelect(id),
                          child: Padding(
                            padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        title,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: theme.textTheme.bodyMedium
                                            ?.copyWith(
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        subtitle,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: theme.textTheme.bodySmall
                                            ?.copyWith(
                                          color: cs.onSurfaceVariant,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.end,
                                  children: [
                                    if (cat.isNotEmpty)
                                      Text(
                                        cat.toUpperCase(),
                                        style:
                                            theme.textTheme.labelSmall?.copyWith(
                                          color: cs.primary,
                                          fontWeight: FontWeight.w700,
                                          letterSpacing: 0.4,
                                          fontSize: 10,
                                        ),
                                      ),
                                    const SizedBox(height: 6),
                                    Container(
                                      width: 8,
                                      height: 8,
                                      decoration: BoxDecoration(
                                        color: _statusColor(f, cs),
                                        shape: BoxShape.circle,
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

class _Facet {
  const _Facet(this.id, this.count);
  final String id;
  final int count;
}

class _CatChip extends StatelessWidget {
  const _CatChip({
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
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (selected) ...[
                Icon(Icons.check, size: 12, color: cs.onPrimary),
                const SizedBox(width: 4),
              ],
              Text(
                label,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: selected ? cs.onPrimary : cs.onSurface,
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
