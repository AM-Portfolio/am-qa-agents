part of 'run_detail_page.dart';

class _BaselineCard extends StatelessWidget {
  const _BaselineCard({required this.baseline});

  final Map<String, dynamic> baseline;

  @override
  Widget build(BuildContext context) {
    final ok = baseline['ok'] == true;
    final message = '${baseline['message'] ?? ''}';
    final prev = baseline['previous'] is Map
        ? Map<String, dynamic>.from(baseline['previous'] as Map)
        : null;
    final compare = baseline['compare'] is Map
        ? Map<String, dynamic>.from(baseline['compare'] as Map)
        : null;

    return GlassCard(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Baseline compare', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          if (!ok)
            Text(
              message.isEmpty ? 'No previous run for this profile.' : message,
              style: Theme.of(context).textTheme.bodySmall,
            )
          else ...[
            if (prev != null) ...[
              Text('Previous run', style: Theme.of(context).textTheme.labelMedium),
              const SizedBox(height: 6),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  Chip(
                    visualDensity: VisualDensity.compact,
                    label: Text(
                      'id ${(prev['id'] ?? '').toString().length > 8 ? prev['id'].toString().substring(0, 8) : prev['id']}',
                    ),
                  ),
                  Chip(
                    visualDensity: VisualDensity.compact,
                    label: Text('${prev['status'] ?? '—'}'),
                  ),
                  Chip(
                    visualDensity: VisualDensity.compact,
                    label: Text(
                      '${_isPlaywrightRun(prev) ? 'Steps' : 'APIs'} ${prev['api_count'] ?? '—'} · '
                      '${prev['api_pass_count'] ?? '—'}✓ / ${prev['api_fail_count'] ?? '—'}✗',
                    ),
                  ),
                  if (prev['passed'] == true)
                    const Chip(
                      visualDensity: VisualDensity.compact,
                      label: Text('passed'),
                      avatar: Icon(Icons.check, size: 14),
                    ),
                  if (prev['passed'] == false)
                    Chip(
                      visualDensity: VisualDensity.compact,
                      label: const Text('failed'),
                      avatar: Icon(
                        Icons.close,
                        size: 14,
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                ],
              ),
            ],
            if (compare != null) ...[
              const SizedBox(height: 12),
              Text('Delta', style: Theme.of(context).textTheme.labelMedium),
              const SizedBox(height: 6),
              _BaselineDelta(compare: compare),
            ],
            const SizedBox(height: 8),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: Text(
                'Raw baseline JSON',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              children: [
                SelectableText(
                  const JsonEncoder.withIndent('  ').convert(baseline),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontFamily: 'monospace',
                      ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _BaselineDelta extends StatelessWidget {
  const _BaselineDelta({required this.compare});

  final Map<String, dynamic> compare;

  @override
  Widget build(BuildContext context) {
    final deltas = <MapEntry<String, dynamic>>[];
    void collect(String prefix, Object? node) {
      if (node is Map) {
        for (final e in node.entries) {
          final key = prefix.isEmpty ? '${e.key}' : '$prefix.${e.key}';
          if (e.value is Map &&
              ((e.value as Map).containsKey('delta') ||
                  (e.value as Map).containsKey('a') ||
                  (e.value as Map).containsKey('b'))) {
            deltas.add(MapEntry(key, e.value));
          } else if (e.value is Map) {
            collect(key, e.value);
          } else if (e.key == 'delta' || e.key == 'diff') {
            deltas.add(MapEntry(prefix, node));
          }
        }
      }
    }

    collect('', compare);
    if (deltas.isEmpty) {
      // Fallback: show a few top-level compare keys as chips
      return Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final e in compare.entries.take(8))
            if (e.key != 'ok' && e.value is! Map)
              Chip(
                visualDensity: VisualDensity.compact,
                label: Text('${e.key}: ${e.value}'),
              ),
          if (compare.entries.every((e) => e.value is Map || e.key == 'ok'))
            Text(
              'See raw JSON for full compare payload.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
        ],
      );
    }

    return Column(
      children: [
        for (final e in deltas.take(12))
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              children: [
                Expanded(
                  child: Text(e.key, style: Theme.of(context).textTheme.bodySmall),
                ),
                Text(
                  e.value is Map
                      ? '${(e.value as Map)['a'] ?? '—'} → ${(e.value as Map)['b'] ?? '—'}'
                          '${(e.value as Map)['delta'] != null ? ' (Δ ${(e.value as Map)['delta']})' : ''}'
                      : '${e.value}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

