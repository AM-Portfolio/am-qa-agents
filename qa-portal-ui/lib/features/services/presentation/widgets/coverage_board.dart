import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../../../core/router/app_router.dart';
import '../../../execute/data/execute_repository.dart';

/// Few runnable SPTs per service (capped). Each SPT expands to pick profile / load / run.
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
  final VoidCallback? onRun;

  @override
  State<CoverageBoard> createState() => _CoverageBoardState();
}

class _CoverageBoardState extends State<CoverageBoard> {
  /// Hard cap — Services page stays scannable; invent/catalog excess is dropped.
  static const _maxSpts = 4;

  static const _preferredIds = <String>[
    'happy_flow',
    'validation',
    'data_generator',
    'openapi_load',
  ];

  static const _fallback = <String, (String, String, String, String)>{
    'data_generator': (
      'SPT 0',
      'Data preparation',
      'Setup',
      'Seed or prepare data this service needs before other checks.',
    ),
    'happy_flow': (
      'SPT 1',
      'Happy path',
      'Functional',
      'Main success journey for a normal user (OpenAPI / invent cases).',
    ),
    'validation': (
      'SPT 2',
      'Input validation',
      'Negative',
      'Bad or incomplete input is rejected with a clear client error.',
    ),
    'openapi_load': (
      'SPT 3',
      'API load (OpenAPI)',
      'Load',
      'k6 against this service OpenAPI surface — pick profile and load below.',
    ),
  };

  static const _loadPresets = <String, (int, int)>{
    '1-call': (1, 1),
    'smoke': (2, 5),
    'light': (5, 20),
    'medium': (10, 50),
    'heavy': (25, 100),
  };

  String? _expandedId = 'openapi_load';
  List<Map<String, dynamic>> _profiles = const [];
  bool _profilesLoading = true;
  String? _profilesError;

  /// Per-SPT run picks (profile id, load key, test type).
  final Map<String, _RunPick> _picks = {};

  @override
  void initState() {
    super.initState();
    _loadProfiles();
  }

  @override
  void didUpdateWidget(covariant CoverageBoard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.serviceId != widget.serviceId ||
        oldWidget.environment != widget.environment) {
      _picks.clear();
      _loadProfiles();
    }
  }

  Future<void> _loadProfiles() async {
    setState(() {
      _profilesLoading = true;
      _profilesError = null;
    });
    try {
      final all = await getIt<ExecuteRepository>().listConfigs();
      final svc = widget.serviceId;
      final matched = all.where((c) {
        final s = '${c['service'] ?? ''}'.trim();
        return s.isEmpty || s == svc;
      }).toList();
      if (!mounted) return;
      setState(() {
        _profiles = matched.isNotEmpty ? matched : all;
        _profilesLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _profiles = const [];
        _profilesLoading = false;
        _profilesError = '$e';
      });
    }
  }

  _RunPick _pickFor(String sptId) {
    return _picks.putIfAbsent(
      sptId,
      () => _RunPick(
        profileId: _defaultProfileId(),
        loadKey: sptId == 'openapi_load' ? 'smoke' : '1-call',
        testType: 'k6',
      ),
    );
  }

  String? _defaultProfileId() {
    if (_profiles.isEmpty) return null;
    final svc = widget.serviceId;
    final hit = _profiles.cast<Map<String, dynamic>?>().firstWhere(
          (c) => '${c?['service'] ?? ''}' == svc,
          orElse: () => null,
        );
    final c = hit ?? _profiles.first;
    return '${c['id'] ?? c['name'] ?? ''}';
  }

  Color _catColor(String cat) {
    switch (cat) {
      case 'Setup':
        return const Color(0xFF5B8DEF);
      case 'Functional':
        return const Color(0xFF3DDC97);
      case 'Negative':
        return const Color(0xFFFFB020);
      case 'Load':
        return const Color(0xFF4DD0E1);
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
        '${skill['level'] ?? _fallback[id]?.$1 ?? 'SPT'}',
        '${skill['display_name'] ?? _fallback[id]?.$2 ?? id}',
        '${skill['category'] ?? _fallback[id]?.$3 ?? 'Other'}',
        '${skill['plain_english'] ?? skill['summary'] ?? _fallback[id]?.$4 ?? ''}',
      );
    }
    final fb = _fallback[id];
    if (fb != null) return fb;
    return ('SPT', id.replaceAll('_', ' '), 'Other', '');
  }

  List<_SuiteView> _buildSuites() {
    final bySkill = <String, List<Map<String, dynamic>>>{};
    for (final u in widget.useCases) {
      final sk = '${u['skill'] ?? ''}'.trim();
      if (sk.isEmpty) continue;
      bySkill.putIfAbsent(sk, () => []).add(u);
    }
    final skillById = <String, Map<String, dynamic>>{
      for (final s in widget.skills) '${s['id']}': s,
    };

    // Always offer the preferred SPT set (capped), then fill from skills if needed.
    final ids = <String>[];
    for (final id in _preferredIds) {
      if (ids.length >= _maxSpts) break;
      ids.add(id);
    }
    for (final s in widget.skills) {
      if (ids.length >= _maxSpts) break;
      final id = '${s['id']}';
      if (id.isEmpty || ids.contains(id)) continue;
      ids.add(id);
    }

    return [
      for (final id in ids)
        _SuiteView(
          id: id,
          level: _meta(id, skillById[id]).$1,
          name: _meta(id, skillById[id]).$2,
          category: _meta(id, skillById[id]).$3,
          plain: _meta(id, skillById[id]).$4,
          cases: bySkill[id] ?? const [],
          alwaysRunnable: id == 'openapi_load' || id == 'happy_flow',
        ),
    ];
  }

  void _openRuns() {
    final svc = widget.serviceId;
    context.go(
      svc.isEmpty ? AppRoutes.runs : '${AppRoutes.runs}?service=$svc',
    );
  }

  void _openProfiles() {
    context.go(AppRoutes.profiles);
  }

  Future<void> _runSpt(_SuiteView suite) async {
    final svc = widget.serviceId;
    if (svc.isEmpty) return;
    final pick = _pickFor(suite.id);
    final load = _loadPresets[pick.loadKey] ?? (1, 1);
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(
      SnackBar(
        content: Text(
          'Starting ${suite.name} · $svc · ${pick.loadKey} '
          '(${load.$1} VUs / ${load.$2} calls)…',
        ),
        behavior: SnackBarBehavior.floating,
      ),
    );
    try {
      final exec = getIt<ExecuteRepository>();
      final out = await exec.execute(
        configId: pick.profileId,
        service: svc,
        audience: 'developer',
        environment: widget.environment,
        testType: pick.testType,
        profile: pick.loadKey == '1-call' ? 'smoke' : 'load',
        vus: load.$1,
        calls: load.$2,
        // openapi_load → all APIs; others → let config drive when profile set
        apiIds: suite.id == 'openapi_load' ? null : null,
      );
      final runId = '${out['id'] ?? out['run_id'] ?? ''}';
      if (runId.isNotEmpty && mounted) {
        context.go('${AppRoutes.runs}/$runId');
      }
    } catch (e) {
      messenger.showSnackBar(
        SnackBar(
          content: Text('Run failed: $e'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final suites = _buildSuites();
    final scheme = Theme.of(context).colorScheme;
    final caseTotal = suites.fold<int>(0, (n, s) => n + s.cases.length);

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
                      'Service SPTs',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${suites.length} max · $caseTotal invent cases · '
                      '${widget.environment} · ${widget.serviceId}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppColors.textSecondaryDark,
                          ),
                    ),
                  ],
                ),
              ),
              OutlinedButton.icon(
                onPressed: _openProfiles,
                icon: const Icon(Icons.tune, size: 18),
                label: Text(
                  _profilesLoading
                      ? 'Profiles…'
                      : 'Profiles (${_profiles.length})',
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                onPressed: _openRuns,
                icon: const Icon(Icons.history, size: 18),
                label: const Text('Runs'),
              ),
            ],
          ),
          if (_profilesError != null) ...[
            const SizedBox(height: 8),
            Text(
              'Profiles unavailable on this backend — run still uses service + load presets.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.amber.shade200,
                  ),
            ),
          ],
          const SizedBox(height: 14),
          for (final suite in suites) ...[
            _SptPanel(
              suite: suite,
              accent: _catColor(suite.category),
              expanded: _expandedId == suite.id,
              pick: _pickFor(suite.id),
              profiles: _profiles,
              loadKeys: _loadPresets.keys.toList(),
              environment: widget.environment,
              serviceId: widget.serviceId,
              surface: scheme.surface,
              outline: scheme.outlineVariant,
              onToggle: () => setState(() {
                _expandedId = _expandedId == suite.id ? null : suite.id;
              }),
              onPickChanged: (p) => setState(() => _picks[suite.id] = p),
              onRun: () => _runSpt(suite),
              onOpenProfiles: _openProfiles,
            ),
            const SizedBox(height: 12),
          ],
        ],
      ),
    );
  }
}

class _RunPick {
  _RunPick({
    this.profileId,
    required this.loadKey,
    required this.testType,
  });

  String? profileId;
  String loadKey;
  String testType;

  _RunPick copyWith({
    String? profileId,
    String? loadKey,
    String? testType,
    bool clearProfile = false,
  }) {
    return _RunPick(
      profileId: clearProfile ? null : (profileId ?? this.profileId),
      loadKey: loadKey ?? this.loadKey,
      testType: testType ?? this.testType,
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
    required this.cases,
    this.alwaysRunnable = false,
  });

  final String id;
  final String level;
  final String name;
  final String category;
  final String plain;
  final List<Map<String, dynamic>> cases;
  final bool alwaysRunnable;
}

class _SptPanel extends StatelessWidget {
  const _SptPanel({
    required this.suite,
    required this.accent,
    required this.expanded,
    required this.pick,
    required this.profiles,
    required this.loadKeys,
    required this.environment,
    required this.serviceId,
    required this.surface,
    required this.outline,
    required this.onToggle,
    required this.onPickChanged,
    required this.onRun,
    required this.onOpenProfiles,
  });

  final _SuiteView suite;
  final Color accent;
  final bool expanded;
  final _RunPick pick;
  final List<Map<String, dynamic>> profiles;
  final List<String> loadKeys;
  final String environment;
  final String serviceId;
  final Color surface;
  final Color outline;
  final VoidCallback onToggle;
  final ValueChanged<_RunPick> onPickChanged;
  final VoidCallback onRun;
  final VoidCallback onOpenProfiles;

  String _profileLabel(Map<String, dynamic> c) {
    final name = '${c['name'] ?? c['id'] ?? 'profile'}';
    final svc = '${c['service'] ?? ''}';
    final aud = '${c['audience'] ?? ''}';
    final bits = <String>[name];
    if (svc.isNotEmpty) bits.add(svc);
    if (aud.isNotEmpty) bits.add(aud);
    return bits.join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    final profileIds = profiles
        .map((c) => '${c['id'] ?? c['name'] ?? ''}')
        .where((id) => id.isNotEmpty)
        .toList();
    final selectedProfile =
        profileIds.contains(pick.profileId) ? pick.profileId : null;

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
                          suite.plain,
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
                            _Tag(
                              suite.cases.isEmpty
                                  ? (suite.alwaysRunnable
                                      ? 'runnable'
                                      : 'no invent cases')
                                  : '${suite.cases.length} invent cases',
                              accent,
                            ),
                            FilledButton.tonalIcon(
                              onPressed: onRun,
                              icon: const Icon(
                                Icons.play_arrow_rounded,
                                size: 18,
                              ),
                              label: const Text('Run SPT'),
                            ),
                          ],
                        ),
                        if (expanded) ...[
                          const SizedBox(height: 14),
                          Divider(color: outline.withValues(alpha: 0.5)),
                          const SizedBox(height: 10),
                          Text(
                            'Run settings',
                            style: Theme.of(context)
                                .textTheme
                                .titleSmall
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 10),
                          Wrap(
                            spacing: 12,
                            runSpacing: 12,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              SizedBox(
                                width: 220,
                                child: InputDecorator(
                                  decoration: const InputDecoration(
                                    labelText: 'Service',
                                    border: OutlineInputBorder(),
                                    isDense: true,
                                  ),
                                  child: Text(
                                    serviceId,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ),
                              SizedBox(
                                width: 120,
                                child: InputDecorator(
                                  decoration: const InputDecoration(
                                    labelText: 'Environment',
                                    border: OutlineInputBorder(),
                                    isDense: true,
                                  ),
                                  child: Text(environment),
                                ),
                              ),
                              SizedBox(
                                width: 140,
                                child: DropdownButtonFormField<String>(
                                  value: pick.testType,
                                  decoration: const InputDecoration(
                                    labelText: 'Test type',
                                    border: OutlineInputBorder(),
                                    isDense: true,
                                  ),
                                  items: const [
                                    DropdownMenuItem(
                                      value: 'k6',
                                      child: Text('API load (k6)'),
                                    ),
                                    DropdownMenuItem(
                                      value: 'playwright',
                                      child: Text('UI (Playwright)'),
                                    ),
                                  ],
                                  onChanged: (v) {
                                    if (v == null) return;
                                    onPickChanged(pick.copyWith(testType: v));
                                  },
                                ),
                              ),
                              SizedBox(
                                width: 140,
                                child: DropdownButtonFormField<String>(
                                  value: loadKeys.contains(pick.loadKey)
                                      ? pick.loadKey
                                      : loadKeys.first,
                                  decoration: const InputDecoration(
                                    labelText: 'Load',
                                    border: OutlineInputBorder(),
                                    isDense: true,
                                  ),
                                  items: [
                                    for (final k in loadKeys)
                                      DropdownMenuItem(
                                        value: k,
                                        child: Text(k),
                                      ),
                                  ],
                                  onChanged: (v) {
                                    if (v == null) return;
                                    onPickChanged(pick.copyWith(loadKey: v));
                                  },
                                ),
                              ),
                              SizedBox(
                                width: 280,
                                child: profiles.isEmpty
                                    ? InputDecorator(
                                        decoration: const InputDecoration(
                                          labelText: 'Profile',
                                          border: OutlineInputBorder(),
                                          isDense: true,
                                        ),
                                        child: TextButton(
                                          onPressed: onOpenProfiles,
                                          child: const Text('Open Profiles'),
                                        ),
                                      )
                                    : DropdownButtonFormField<String>(
                                        value: selectedProfile,
                                        isExpanded: true,
                                        decoration: const InputDecoration(
                                          labelText: 'Profile',
                                          border: OutlineInputBorder(),
                                          isDense: true,
                                        ),
                                        items: [
                                          for (final c in profiles)
                                            DropdownMenuItem(
                                              value:
                                                  '${c['id'] ?? c['name'] ?? ''}',
                                              child: Text(
                                                _profileLabel(c),
                                                overflow: TextOverflow.ellipsis,
                                              ),
                                            ),
                                        ],
                                        onChanged: (v) {
                                          onPickChanged(
                                            pick.copyWith(
                                              profileId: v,
                                              clearProfile: v == null,
                                            ),
                                          );
                                        },
                                      ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Align(
                            alignment: Alignment.centerRight,
                            child: FilledButton.icon(
                              onPressed: onRun,
                              icon: const Icon(Icons.play_arrow_rounded),
                              label: Text('Run ${suite.name}'),
                            ),
                          ),
                          if (suite.cases.isNotEmpty) ...[
                            const SizedBox(height: 14),
                            Text(
                              'Invent cases (${suite.cases.length})',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleSmall
                                  ?.copyWith(fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 6),
                            for (var i = 0;
                                i < suite.cases.length && i < 6;
                                i++)
                              Padding(
                                padding: const EdgeInsets.only(bottom: 4),
                                child: Text(
                                  '• ${suite.cases[i]['title'] ?? suite.cases[i]['id'] ?? 'case'}',
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ),
                            if (suite.cases.length > 6)
                              Text(
                                '+${suite.cases.length - 6} more',
                                style: Theme.of(context)
                                    .textTheme
                                    .labelSmall
                                    ?.copyWith(color: accent),
                              ),
                          ] else ...[
                            const SizedBox(height: 10),
                            Text(
                              suite.alwaysRunnable
                                  ? 'No invent cases on this agent — SPT still runs via OpenAPI / profile.'
                                  : 'No invent cases for this SPT on Contabo dig yet. Use API load SPT or sync invent locally.',
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: AppColors.textSecondaryDark,
                                  ),
                            ),
                          ],
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
