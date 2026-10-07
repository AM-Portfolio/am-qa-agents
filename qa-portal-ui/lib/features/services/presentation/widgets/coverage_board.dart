import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';

/// Category → suites → plain-English cases (Services + Specs Use cases tab).
class CoverageBoard extends StatefulWidget {
  const CoverageBoard({
    super.key,
    required this.skills,
    required this.useCases,
    required this.serviceId,
    required this.environment,
    this.onRun,
  });

  final List<Map<String, dynamic>> skills;
  final List<Map<String, dynamic>> useCases;
  final String serviceId;
  final String environment;
  /// When set (e.g. Specs), used instead of the Execute-bar snackbar.
  final VoidCallback? onRun;

  @override
  State<CoverageBoard> createState() => _CoverageBoardState();
}

class _CoverageBoardState extends State<CoverageBoard> {
  static const _categories = <String>[
    'All',
    'Setup',
    'Functional',
    'Negative',
    'Boundary',
    'Integration',
    'Security',
    'Catalog',
  ];

  static const _fallback = <String, (String, String, String, String)>{
    'data_generator': (
      'Level 0',
      'Data preparation',
      'Setup',
      'Create or seed the data this service needs before other tests run.',
    ),
    'happy_flow': (
      'Level 1',
      'Happy path validation',
      'Functional',
      'Confirm the main success journey works end-to-end for a normal user.',
    ),
    'level2_alt_path': (
      'Level 2',
      'Alternate path validation',
      'Functional',
      'Confirm a different valid order of calls still reaches a good outcome.',
    ),
    'validation': (
      'Level 2',
      'Input validation',
      'Negative',
      'Confirm bad or incomplete input is rejected with a clear client error.',
    ),
    'level3_edge': (
      'Level 3',
      'Edge case validation',
      'Boundary',
      'Confirm awkward but legal values and boundary conditions behave safely.',
    ),
    'null_point': (
      'Level 3',
      'Missing resource validation',
      'Negative',
      'Confirm unknown or missing resources return not-found or empty results.',
    ),
    'tweak_data': (
      'Level 3',
      'State change validation',
      'Functional',
      'Confirm a small legitimate update changes what the service returns later.',
    ),
    'level4_state': (
      'Level 4',
      'Lifecycle validation',
      'Integration',
      'Confirm multi-step lifecycle transitions (pause, resume, cancel, upgrade).',
    ),
    'level5_abuse': (
      'Level 5',
      'Abuse & illegal transition',
      'Security',
      'Confirm illegal or abusive state toggles are blocked without breaking the service.',
    ),
    'security': (
      'Level 5',
      'Auth & access control',
      'Security',
      'Confirm protected APIs reject missing or wrong credentials.',
    ),
  };

  String _category = 'All';
  final Set<String> _expanded = {'happy_flow'};

  Color _catColor(String cat) {
    switch (cat) {
      case 'Setup':
        return const Color(0xFF5B8DEF);
      case 'Functional':
        return const Color(0xFF3DDC97);
      case 'Negative':
        return const Color(0xFFFFB020);
      case 'Boundary':
        return const Color(0xFFB388FF);
      case 'Integration':
        return const Color(0xFF4DD0E1);
      case 'Security':
        return const Color(0xFFFF6B6B);
      case 'Catalog':
        return const Color(0xFF90A4AE);
      default:
        return AppColors.primary;
    }
  }

  (String level, String name, String category, String plain) _meta(
    String id,
    Map<String, dynamic>? skill,
  ) {
    if (skill != null) {
      return (
        '${skill['level'] ?? _fallback[id]?.$1 ?? 'Suite'}',
        '${skill['display_name'] ?? _fallback[id]?.$2 ?? id}',
        '${skill['category'] ?? _fallback[id]?.$3 ?? 'Other'}',
        '${skill['plain_english'] ?? skill['summary'] ?? _fallback[id]?.$4 ?? ''}',
      );
    }
    final fb = _fallback[id];
    if (fb != null) return fb;
    return ('Suite', id.replaceAll('_', ' '), 'Other', '');
  }

  String _plainTitle(String raw) {
    var t = raw.trim();
    if (t.toLowerCase().startsWith('seed:')) {
      return 'Baseline seed for this suite';
    }
    if (t.isEmpty) return 'Untitled test case';
    // already sentence-like from invent
    if (t.contains(' ') && !t.startsWith('/')) return t;
    return t.replaceAll('_', ' ');
  }

  String _plainStep(String step) {
    final s = step.trim();
    if (s.isEmpty) return 'No API call recorded';
    final m = RegExp(r'^(GET|POST|PUT|PATCH|DELETE|HEAD)\s+(.+)$', caseSensitive: false)
        .firstMatch(s);
    if (m == null) return s;
    final method = m.group(1)!.toUpperCase();
    final path = m.group(2)!.trim();
    final leaf = path.split('?').first.split('/').where((p) => p.isNotEmpty).toList();
    final tip = leaf.isEmpty ? 'resource' : leaf.last.replaceAll('-', ' ').replaceAll('_', ' ');
    switch (method) {
      case 'GET':
        return 'Read $tip';
      case 'POST':
        return 'Create or submit $tip';
      case 'PUT':
      case 'PATCH':
        return 'Update $tip';
      case 'DELETE':
        return 'Delete $tip';
      default:
        return '$method $tip';
    }
  }

  void _openRuns() {
    final svc = widget.serviceId;
    if (svc.isEmpty) {
      context.go(AppRoutes.runs);
      return;
    }
    context.go('${AppRoutes.runs}?service=$svc');
  }

  void _openOpenApi() {
    final svc = widget.serviceId;
    context.go(svc.isEmpty ? AppRoutes.specs : '${AppRoutes.specs}?spec=$svc');
  }

  void _focusExecute() {
    if (widget.onRun != null) {
      widget.onRun!();
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Use the Execute bar above to run ${widget.serviceId.isEmpty ? 'this service' : widget.serviceId} '
          '(${widget.environment}). Choose a config, then press Run.',
        ),
        behavior: SnackBarBehavior.floating,
        action: SnackBarAction(label: 'All runs', onPressed: _openRuns),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bySkill = <String, List<Map<String, dynamic>>>{};
    final orphan = <Map<String, dynamic>>[];
    for (final u in widget.useCases) {
      final sk = '${u['skill'] ?? ''}'.trim();
      if (sk.isEmpty) {
        orphan.add(u);
      } else {
        bySkill.putIfAbsent(sk, () => []).add(u);
      }
    }
    final skillById = <String, Map<String, dynamic>>{
      for (final s in widget.skills) '${s['id']}': s,
    };
    final suiteIds = <String>[
      for (final s in widget.skills) '${s['id']}',
      for (final id in bySkill.keys)
        if (!skillById.containsKey(id)) id,
    ];

    final suites = <_SuiteView>[
      for (final id in suiteIds)
        _SuiteView(
          id: id,
          level: _meta(id, skillById[id]).$1,
          name: _meta(id, skillById[id]).$2,
          category: _meta(id, skillById[id]).$3,
          plain: _meta(id, skillById[id]).$4,
          envAction: '${skillById[id]?['env_action'] ?? 'run'}',
          cases: bySkill[id] ?? const [],
        ),
      if (orphan.isNotEmpty)
        _SuiteView(
          id: 'catalog',
          level: 'Catalog',
          name: 'Service catalog flows',
          category: 'Catalog',
          plain: 'Hand-authored flows from the service plugin catalog.',
          envAction: 'run',
          cases: orphan,
        ),
    ];

    final filtered = _category == 'All'
        ? suites
        : suites.where((s) => s.category == _category).toList();
    final totalCases =
        filtered.fold<int>(0, (n, s) => n + s.cases.length);

    final scheme = Theme.of(context).colorScheme;

    return GlassCard(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Test suites',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${filtered.length} suites Â· $totalCases test cases Â· ${widget.environment}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppColors.textSecondaryDark,
                          ),
                    ),
                  ],
                ),
              ),
              OutlinedButton.icon(
                onPressed: _openRuns,
                icon: const Icon(Icons.history, size: 18),
                label: const Text('All runs'),
              ),
              const SizedBox(width: 8),
              FilledButton.icon(
                onPressed: _focusExecute,
                icon: const Icon(Icons.play_arrow_rounded, size: 20),
                label: const Text('Run'),
              ),
            ],
          ),
          const SizedBox(height: 14),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final cat in _categories)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(cat),
                      selected: _category == cat,
                      onSelected: (_) => setState(() => _category = cat),
                      selectedColor: _catColor(cat).withValues(alpha: 0.28),
                      labelStyle: TextStyle(
                        fontWeight:
                            _category == cat ? FontWeight.w700 : FontWeight.w500,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          if (filtered.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: Text(
                'No suites in this category yet.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppColors.textSecondaryDark,
                    ),
              ),
            )
          else
            for (final suite in filtered) ...[
              _SuitePanel(
                suite: suite,
                accent: _catColor(suite.category),
                expanded: _expanded.contains(suite.id),
                onToggle: () => setState(() {
                  if (_expanded.contains(suite.id)) {
                    _expanded.remove(suite.id);
                  } else {
                    _expanded.add(suite.id);
                  }
                }),
                onRun: _focusExecute,
                onAllRuns: _openRuns,
                onOpenApi: _openOpenApi,
                plainTitle: _plainTitle,
                plainStep: _plainStep,
                surface: scheme.surface,
                outline: scheme.outlineVariant,
              ),
              const SizedBox(height: 12),
            ],
        ],
      ),
    );
  }
}

class _SuiteView {
  const _SuiteView({
    required this.id,
    required this.level,
    required this.name,
    required this.category,
    required this.plain,
    required this.envAction,
    required this.cases,
  });

  final String id;
  final String level;
  final String name;
  final String category;
  final String plain;
  final String envAction;
  final List<Map<String, dynamic>> cases;
}

class _SuitePanel extends StatelessWidget {
  const _SuitePanel({
    required this.suite,
    required this.accent,
    required this.expanded,
    required this.onToggle,
    required this.onRun,
    required this.onAllRuns,
    required this.onOpenApi,
    required this.plainTitle,
    required this.plainStep,
    required this.surface,
    required this.outline,
  });

  final _SuiteView suite;
  final Color accent;
  final bool expanded;
  final VoidCallback onToggle;
  final VoidCallback onRun;
  final VoidCallback onAllRuns;
  final VoidCallback onOpenApi;
  final String Function(String) plainTitle;
  final String Function(String) plainStep;
  final Color surface;
  final Color outline;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: surface.withValues(alpha: 0.35),
      borderRadius: BorderRadius.circular(14),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onToggle,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: outline.withValues(alpha: 0.4)),
          ),
          clipBehavior: Clip.antiAlias,
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(width: 5, color: accent),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
                    child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: accent.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      suite.level,
                      style: TextStyle(
                        color: accent,
                        fontWeight: FontWeight.w800,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      suite.name,
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                      ),
                    ),
                  ),
                  Icon(
                    expanded
                        ? Icons.expand_less_rounded
                        : Icons.expand_more_rounded,
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                suite.plain.isEmpty
                    ? 'Suite of automated checks for this service.'
                    : suite.plain,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppColors.textSecondaryDark,
                      height: 1.35,
                    ),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  _Tag(suite.category, accent),
                  _Tag('${suite.cases.length} test cases', accent),
                  _Tag('Policy: ${suite.envAction}', accent),
                  TextButton.icon(
                    onPressed: onAllRuns,
                    icon: const Icon(Icons.history, size: 16),
                    label: const Text('Runs'),
                  ),
                  FilledButton.tonalIcon(
                    onPressed: onRun,
                    icon: const Icon(Icons.play_arrow_rounded, size: 18),
                    label: const Text('Run suite'),
                  ),
                ],
              ),
              if (expanded) ...[
                const SizedBox(height: 14),
                Divider(color: outline.withValues(alpha: 0.5)),
                const SizedBox(height: 10),
                Text(
                  'Test cases',
                  style: Theme.of(context)
                      .textTheme
                      .titleSmall
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                if (suite.cases.isEmpty)
                  Text(
                    'No invented cases in this suite yet.',
                    style: Theme.of(context).textTheme.bodySmall,
                  )
                else
                  GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: suite.cases.length,
                    gridDelegate:
                        const SliverGridDelegateWithMaxCrossAxisExtent(
                      maxCrossAxisExtent: 340,
                      mainAxisExtent: 188,
                      crossAxisSpacing: 10,
                      mainAxisSpacing: 10,
                    ),
                    itemBuilder: (context, i) => _CaseCard(
                      index: i + 1,
                      data: suite.cases[i],
                      accent: accent,
                      plainTitle: plainTitle,
                      plainStep: plainStep,
                      onOpenApi: onOpenApi,
                      onRun: onRun,
                    ),
                  ),
              ],
            ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _CaseCard extends StatelessWidget {
  const _CaseCard({
    required this.index,
    required this.data,
    required this.accent,
    required this.plainTitle,
    required this.plainStep,
    required this.onOpenApi,
    required this.onRun,
  });

  final int index;
  final Map<String, dynamic> data;
  final Color accent;
  final String Function(String) plainTitle;
  final String Function(String) plainStep;
  final VoidCallback onOpenApi;
  final VoidCallback onRun;

  @override
  Widget build(BuildContext context) {
    final steps = (data['steps_preview'] is List)
        ? (data['steps_preview'] as List).map((e) => '$e').toList()
        : <String>[];
    final title = plainTitle('${data['title'] ?? data['id'] ?? 'Test case'}');
    final englishSteps = steps.isEmpty
        ? <String>['No API steps recorded for this case.']
        : steps.map(plainStep).toList();
    final shown = englishSteps.take(3).toList();
    final more = englishSteps.length - shown.length;

    return Container(
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.55),
        border: Border.all(color: accent.withValues(alpha: 0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 20,
                height: 20,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.22),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '$index',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    color: accent,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                    height: 1.2,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (var i = 0; i < shown.length; i++)
                  Text(
                    '${i + 1}. ${shown[i]}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          height: 1.25,
                          color: AppColors.textSecondaryDark,
                        ),
                  ),
                if (more > 0)
                  Text(
                    '+$more more',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: accent,
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                if (steps.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    steps.join(' â†’ '),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: AppColors.textSecondaryDark
                              .withValues(alpha: 0.85),
                          fontFamily: 'monospace',
                        ),
                  ),
                ],
              ],
            ),
          ),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: onOpenApi,
                  style: OutlinedButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    minimumSize: const Size(0, 32),
                  ),
                  child: const Text('View API', style: TextStyle(fontSize: 11.5)),
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: FilledButton.tonal(
                  onPressed: onRun,
                  style: FilledButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    minimumSize: const Size(0, 32),
                  ),
                  child: const Text('Run', style: TextStyle(fontSize: 11.5)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag(this.text, this.color);

  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 11.5,
          fontWeight: FontWeight.w600,
          color: color.withValues(alpha: 0.95),
        ),
      ),
    );
  }
}

