import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/router/app_router.dart';
import 'package:am_design_system/am_design_system.dart';

part 'coverage_suite.part.dart';
part 'coverage_case.part.dart';

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

