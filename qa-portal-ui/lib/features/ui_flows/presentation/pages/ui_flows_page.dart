import 'dart:convert';

import 'package:am_design_system/am_design_system.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../../execute/data/execute_repository.dart';
import '../../data/ui_flows_repository.dart';

final _flowIdPattern = RegExp(r'^[A-Z0-9_]+$');

class UiFlowsPage extends StatelessWidget {
  const UiFlowsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => UiFlowsCubit(getIt<UiFlowsRepository>())..load(),
      child: const _UiFlowsView(),
    );
  }
}

class UiFlowsState extends Equatable {
  const UiFlowsState({
    this.loading = false,
    this.agentOnline = false,
    this.agentUrl,
    this.error,
    this.flows = const [],
    this.suites = const [],
  });

  final bool loading;
  final bool agentOnline;
  final String? agentUrl;
  final String? error;
  final List<Map<String, dynamic>> flows;
  final List<Map<String, dynamic>> suites;

  UiFlowsState copyWith({
    bool? loading,
    bool? agentOnline,
    String? agentUrl,
    String? error,
    List<Map<String, dynamic>>? flows,
    List<Map<String, dynamic>>? suites,
  }) {
    return UiFlowsState(
      loading: loading ?? this.loading,
      agentOnline: agentOnline ?? this.agentOnline,
      agentUrl: agentUrl ?? this.agentUrl,
      error: error,
      flows: flows ?? this.flows,
      suites: suites ?? this.suites,
    );
  }

  @override
  List<Object?> get props => [loading, agentOnline, agentUrl, error, flows, suites];
}

class UiFlowsCubit extends Cubit<UiFlowsState> {
  UiFlowsCubit(this._repo) : super(const UiFlowsState());

  final UiFlowsRepository _repo;

  Future<void> load() async {
    emit(state.copyWith(loading: true, error: null));
    try {
      final cat = await _repo.catalog();
      final flows = <Map<String, dynamic>>[];
      final seen = <String>{};

      void addMap(Map raw) {
        final m = Map<String, dynamic>.from(raw);
        final id = '${m['id'] ?? ''}'.trim();
        if (id.isEmpty) return;
        if (!seen.add(id)) {
          final idx = flows.indexWhere((f) => '${f['id']}' == id);
          if (idx >= 0) {
            // Prefer richer map (more keys) over stub.
            if (m.keys.length >= flows[idx].keys.length) {
              flows[idx] = m;
            }
          }
          return;
        }
        flows.add(m);
      }

      void addStub(String id) {
        final trimmed = id.trim();
        if (trimmed.isEmpty || seen.contains(trimmed)) return;
        seen.add(trimmed);
        flows.add({'id': trimmed, 'label': trimmed});
      }

      // Prefer full maps from flows + custom_flows first.
      for (final key in ['flows', 'custom_flows']) {
        final list = cat[key];
        if (list is! List) continue;
        for (final e in list) {
          if (e is Map) addMap(e);
        }
      }
      // Then other buckets: maps upgrade stubs; strings only if unseen.
      for (final key in ['deterministic', 'release_gate']) {
        final list = cat[key];
        if (list is! List) continue;
        for (final e in list) {
          if (e is Map) {
            addMap(e);
          } else if (e is String) {
            addStub(e);
          }
        }
      }

      final suites = <Map<String, dynamic>>[];
      final suiteSeen = <String>{};
      final rawSuites = cat['suites'];
      if (rawSuites is List) {
        for (final e in rawSuites) {
          if (e is Map) {
            final m = Map<String, dynamic>.from(e);
            final id = '${m['id'] ?? ''}'.trim();
            if (id.isEmpty || !suiteSeen.add(id)) continue;
            suites.add(m);
          } else if (e is String) {
            final id = e.trim();
            if (id.isEmpty || !suiteSeen.add(id)) continue;
            suites.add({'id': id, 'label': id});
          }
        }
      }
      final agent = cat['agent'];
      final agentMap = agent is Map ? Map<String, dynamic>.from(agent) : null;
      final online = agentMap?['online'] == true || cat['agent_online'] == true;
      final url = agentMap?['url']?.toString() ?? cat['agent_url']?.toString();
      final err = agentMap?['error']?.toString() ?? cat['error']?.toString();
      emit(
        state.copyWith(
          loading: false,
          flows: flows,
          suites: suites,
          agentOnline: online,
          agentUrl: url,
          error: err,
        ),
      );
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }

  Future<void> saveFlow(Map<String, dynamic> body) async {
    final id = body['id']?.toString().trim() ?? '';
    if (id.isEmpty) throw ArgumentError('Flow id required');
    if (!_flowIdPattern.hasMatch(id)) {
      throw ArgumentError('Flow id must match [A-Z0-9_]+');
    }
    final exists = state.flows.any((f) => '${f['id']}' == id);
    final runsAs = body['runs_as']?.toString().trim();
    if (runsAs != null && runsAs.isNotEmpty) {
      final known =
          runsAs == id || state.flows.any((f) => '${f['id']}' == runsAs);
      if (!known) {
        throw ArgumentError('runs_as "$runsAs" is not a known flow id');
      }
    }
    if (exists) {
      await _repo.updateFlow(id, body);
    } else {
      await _repo.createFlow(body);
    }
    await load();
  }

  Future<void> saveSuite(Map<String, dynamic> body) async {
    final id = body['id']?.toString().trim() ?? '';
    if (id.isEmpty) throw ArgumentError('Suite id required');
    if (!_flowIdPattern.hasMatch(id)) {
      throw ArgumentError('Suite id must match [A-Z0-9_]+');
    }
    final profiles = body['profiles'];
    if (profiles is! List || profiles.isEmpty) {
      throw ArgumentError('Suite profiles must be a non-empty list');
    }
    final knownIds = state.flows.map((f) => '${f['id']}').toSet();
    for (final p in profiles) {
      final pid = '$p'.trim();
      if (pid.isEmpty || !knownIds.contains(pid)) {
        throw ArgumentError('Unknown flow profile "$pid"');
      }
    }
    final agentSuite = '${body['agent_suite'] ?? ''}'.trim();
    if (agentSuite != 'smoke' && agentSuite != 'release_gate') {
      throw ArgumentError('agent_suite must be smoke or release_gate');
    }
    final exists = state.suites.any((s) => '${s['id']}' == id);
    if (exists) {
      await _repo.updateSuite(id, body);
    } else {
      await _repo.createSuite(body);
    }
    await load();
  }

  Future<void> deleteFlow(String id, {bool reset = false}) async {
    await _repo.deleteFlow(id, reset: reset);
    await load();
  }

  Future<void> deleteSuite(String id, {bool reset = false}) async {
    await _repo.deleteSuite(id, reset: reset);
    await load();
  }
}

String _jsonArrayText(dynamic value) {
  if (value is List) {
    return const JsonEncoder.withIndent('  ').convert(value);
  }
  return '[]';
}

List<dynamic> _parseJsonArray(String text, String field) {
  final trimmed = text.trim();
  if (trimmed.isEmpty) return [];
  final decoded = jsonDecode(trimmed);
  if (decoded is! List) {
    throw FormatException('$field must be a JSON array');
  }
  return decoded;
}

bool _isUiTestConfig(Map<String, dynamic> config) {
  final testType = '${config['test_type'] ?? 'k6'}'.toLowerCase();
  return testType == 'playwright' || testType == 'mixed';
}

Map<String, dynamic>? _findPlaywrightConfig(List<Map<String, dynamic>> configs) {
  for (final c in configs) {
    if (_isUiTestConfig(c) && '${c['service'] ?? ''}' == 'am-modern-ui') {
      return c;
    }
  }
  for (final c in configs) {
    if (_isUiTestConfig(c)) return c;
  }
  return null;
}

int _listLen(dynamic v) => v is List ? v.length : 0;

class _UiFlowsView extends StatefulWidget {
  const _UiFlowsView();

  @override
  State<_UiFlowsView> createState() => _UiFlowsViewState();
}

class _UiFlowsViewState extends State<_UiFlowsView>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  String _query = '';
  String? _groupFilter;
  String? _selectedFlowId;
  String? _selectedSuiteId;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _tabs.addListener(() {
      if (_tabs.indexIsChanging) return;
      setState(() {});
    });
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _playFlow(BuildContext context, String flowId) async {
    if (flowId.isEmpty) return;
    final executeRepo = getIt<ExecuteRepository>();
    try {
      final configs = await executeRepo.listConfigs();
      final cfg = _findPlaywrightConfig(configs);
      if (cfg == null) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('No playwright/mixed config found')),
          );
        }
        return;
      }
      final configId = '${cfg['id'] ?? ''}';
      if (configId.isEmpty) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('No playwright/mixed config found')),
          );
        }
        return;
      }
      final out = await executeRepo.execute(
        configId: configId,
        testType: 'playwright',
        uiProfile: flowId,
      );
      final runId = '${out['id'] ?? out['run_id'] ?? ''}';
      if (context.mounted && runId.isNotEmpty) {
        context.go('/runs/$runId');
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }

  Future<void> _playSuite(BuildContext context, String suiteId) async {
    if (suiteId.isEmpty) return;
    final executeRepo = getIt<ExecuteRepository>();
    try {
      final configs = await executeRepo.listConfigs();
      final cfg = _findPlaywrightConfig(configs);
      if (cfg == null) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('No playwright/mixed config found')),
          );
        }
        return;
      }
      final configId = '${cfg['id'] ?? ''}';
      if (configId.isEmpty) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('No playwright/mixed config found')),
          );
        }
        return;
      }
      final out = await executeRepo.execute(
        configId: configId,
        testType: 'playwright',
        uiSuite: suiteId,
      );
      final runId = '${out['id'] ?? out['run_id'] ?? ''}';
      if (context.mounted && runId.isNotEmpty) {
        context.go('/runs/$runId');
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }

  Future<void> _editFlow(
    BuildContext context, {
    Map<String, dynamic>? existing,
  }) async {
    final cubit = context.read<UiFlowsCubit>();
    final idCtrl = TextEditingController(text: '${existing?['id'] ?? ''}');
    final labelCtrl = TextEditingController(text: '${existing?['label'] ?? ''}');
    final summaryCtrl =
        TextEditingController(text: '${existing?['summary'] ?? ''}');
    final groupCtrl = TextEditingController(text: '${existing?['group'] ?? ''}');
    final runsAsCtrl =
        TextEditingController(text: '${existing?['runs_as'] ?? ''}');
    final stepsCtrl =
        TextEditingController(text: _jsonArrayText(existing?['steps']));
    final verificationsCtrl =
        TextEditingController(text: _jsonArrayText(existing?['verifications']));
    String? dialogError;

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setLocal) => AlertDialog(
          title: Text(existing == null ? 'New flow' : 'Edit flow'),
          content: SizedBox(
            width: 520,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (dialogError != null) ...[
                    Text(
                      dialogError!,
                      style: TextStyle(color: Theme.of(ctx).colorScheme.error),
                    ),
                    const SizedBox(height: 8),
                  ],
                  TextField(
                    controller: idCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Id (A-Z0-9_)',
                      border: OutlineInputBorder(),
                    ),
                    enabled: existing == null,
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: labelCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Label',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: groupCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Group',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: summaryCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Summary',
                      border: OutlineInputBorder(),
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: runsAsCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Runs as (known flow id or empty)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: stepsCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Steps (JSON array)',
                      hintText: '[{"action": "click", "selector": "#btn"}]',
                      border: OutlineInputBorder(),
                      alignLabelWithHint: true,
                    ),
                    maxLines: 6,
                    minLines: 3,
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: verificationsCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Verifications (JSON array)',
                      hintText: '[{"type": "visible", "selector": "#ok"}]',
                      border: OutlineInputBorder(),
                      alignLabelWithHint: true,
                    ),
                    maxLines: 4,
                    minLines: 2,
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                try {
                  final id = idCtrl.text.trim();
                  if (id.isEmpty) throw ArgumentError('Flow id required');
                  if (!_flowIdPattern.hasMatch(id)) {
                    throw ArgumentError('Flow id must match [A-Z0-9_]+');
                  }
                  if (existing == null &&
                      cubit.state.flows.any((f) => '${f['id']}' == id)) {
                    throw ArgumentError('Flow id already exists');
                  }
                  _parseJsonArray(stepsCtrl.text, 'Steps');
                  _parseJsonArray(verificationsCtrl.text, 'Verifications');
                  final runsAs = runsAsCtrl.text.trim();
                  if (runsAs.isNotEmpty &&
                      !cubit.state.flows.any((f) => '${f['id']}' == runsAs) &&
                      runsAs != id) {
                    throw ArgumentError('runs_as "$runsAs" is not a known flow id');
                  }
                  Navigator.pop(ctx, true);
                } catch (e) {
                  setLocal(() => dialogError = '$e');
                }
              },
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
    if (ok != true || !context.mounted) return;
    try {
      final steps = _parseJsonArray(stepsCtrl.text, 'Steps');
      final verifications = _parseJsonArray(verificationsCtrl.text, 'Verifications');
      await cubit.saveFlow({
        'id': idCtrl.text.trim(),
        'label': labelCtrl.text.trim(),
        'summary': summaryCtrl.text.trim(),
        if (groupCtrl.text.trim().isNotEmpty) 'group': groupCtrl.text.trim(),
        if (runsAsCtrl.text.trim().isNotEmpty) 'runs_as': runsAsCtrl.text.trim(),
        'steps': steps,
        'verifications': verifications,
      });
      setState(() => _selectedFlowId = idCtrl.text.trim());
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }

  Future<void> _editSuite(
    BuildContext context, {
    Map<String, dynamic>? existing,
  }) async {
    final cubit = context.read<UiFlowsCubit>();
    final idCtrl = TextEditingController(text: '${existing?['id'] ?? ''}');
    final labelCtrl = TextEditingController(text: '${existing?['label'] ?? ''}');
    final profiles = existing?['profiles'];
    final profilesCtrl = TextEditingController(
      text: profiles is List ? profiles.join(', ') : '',
    );
    final agentSuite = '${existing?['agent_suite'] ?? 'smoke'}';
    var selectedAgentSuite =
        (agentSuite == 'release_gate') ? 'release_gate' : 'smoke';
    String? dialogError;

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setLocal) => AlertDialog(
          title: Text(existing == null ? 'New suite' : 'Edit suite'),
          content: SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (dialogError != null) ...[
                  Text(
                    dialogError!,
                    style: TextStyle(color: Theme.of(ctx).colorScheme.error),
                  ),
                  const SizedBox(height: 8),
                ],
                TextField(
                  controller: idCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Id (A-Z0-9_)',
                    border: OutlineInputBorder(),
                  ),
                  enabled: existing == null,
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: labelCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Label',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: profilesCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Profiles (comma-separated flow ids)',
                    border: OutlineInputBorder(),
                  ),
                  maxLines: 2,
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  initialValue: selectedAgentSuite,
                  decoration: const InputDecoration(
                    labelText: 'Agent suite',
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'smoke', child: Text('smoke')),
                    DropdownMenuItem(
                      value: 'release_gate',
                      child: Text('release_gate'),
                    ),
                  ],
                  onChanged: (v) {
                    if (v != null) setLocal(() => selectedAgentSuite = v);
                  },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                try {
                  final id = idCtrl.text.trim();
                  if (id.isEmpty) throw ArgumentError('Suite id required');
                  if (!_flowIdPattern.hasMatch(id)) {
                    throw ArgumentError('Suite id must match [A-Z0-9_]+');
                  }
                  final profileList = profilesCtrl.text
                      .split(',')
                      .map((e) => e.trim())
                      .where((e) => e.isNotEmpty)
                      .toList();
                  if (profileList.isEmpty) {
                    throw ArgumentError('At least one profile required');
                  }
                  final known = cubit.state.flows.map((f) => '${f['id']}').toSet();
                  for (final p in profileList) {
                    if (!known.contains(p)) {
                      throw ArgumentError('Unknown flow profile "$p"');
                    }
                  }
                  Navigator.pop(ctx, true);
                } catch (e) {
                  setLocal(() => dialogError = '$e');
                }
              },
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
    if (ok != true || !context.mounted) return;
    final profileList = profilesCtrl.text
        .split(',')
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
    try {
      await cubit.saveSuite({
        'id': idCtrl.text.trim(),
        'label': labelCtrl.text.trim(),
        'profiles': profileList,
        'agent_suite': selectedAgentSuite,
      });
      setState(() {
        _tabs.index = 1;
        _selectedSuiteId = idCtrl.text.trim();
      });
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }

  List<Map<String, dynamic>> _filteredFlows(UiFlowsState state) {
    final q = _query.trim().toLowerCase();
    return state.flows.where((f) {
      final group = '${f['group'] ?? ''}'.trim();
      if (_groupFilter != null && _groupFilter!.isNotEmpty && group != _groupFilter) {
        return false;
      }
      if (q.isEmpty) return true;
      final hay =
          '${f['id']} ${f['label']} ${f['summary']} $group'.toLowerCase();
      return hay.contains(q);
    }).toList();
  }

  List<Map<String, dynamic>> _filteredSuites(UiFlowsState state) {
    final q = _query.trim().toLowerCase();
    if (q.isEmpty) return state.suites;
    return state.suites.where((s) {
      final profiles = s['profiles'];
      final hay =
          '${s['id']} ${s['label']} ${s['agent_suite']} ${profiles is List ? profiles.join(' ') : ''}'
              .toLowerCase();
      return hay.contains(q);
    }).toList();
  }

  Set<String> _groups(UiFlowsState state) {
    final g = <String>{};
    for (final f in state.flows) {
      final group = '${f['group'] ?? ''}'.trim();
      if (group.isNotEmpty) g.add(group);
    }
    return g;
  }

  Map<String, List<Map<String, dynamic>>> _groupFlows(
    List<Map<String, dynamic>> flows,
  ) {
    final map = <String, List<Map<String, dynamic>>>{};
    for (final f in flows) {
      final g = '${f['group'] ?? ''}'.trim();
      final key = g.isEmpty ? 'Ungrouped' : g;
      map.putIfAbsent(key, () => []).add(f);
    }
    final keys = map.keys.toList()
      ..sort((a, b) {
        if (a == 'Ungrouped') return 1;
        if (b == 'Ungrouped') return -1;
        return a.compareTo(b);
      });
    return {for (final k in keys) k: map[k]!};
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: BlocBuilder<UiFlowsCubit, UiFlowsState>(
        builder: (context, state) {
          final flows = _filteredFlows(state);
          final suites = _filteredSuites(state);
          final groups = _groups(state);
          final grouped = _groupFlows(flows);

          Map<String, dynamic>? selectedFlow;
          for (final f in state.flows) {
            if ('${f['id']}' == _selectedFlowId) {
              selectedFlow = f;
              break;
            }
          }
          Map<String, dynamic>? selectedSuite;
          for (final s in state.suites) {
            if ('${s['id']}' == _selectedSuiteId) {
              selectedSuite = s;
              break;
            }
          }

          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              GlassCard(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      'UI flows',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                    Chip(
                      visualDensity: VisualDensity.compact,
                      label: Text(
                        state.agentOnline ? 'agent online' : 'agent offline',
                      ),
                      backgroundColor: state.agentOnline
                          ? AppColors.primary.withValues(alpha: 0.15)
                          : Theme.of(context).colorScheme.errorContainer,
                    ),
                    if (state.agentUrl != null)
                      Text(
                        state.agentUrl!,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    SizedBox(
                      width: 220,
                      child: TextField(
                        decoration: const InputDecoration(
                          labelText: 'Search',
                          isDense: true,
                          border: OutlineInputBorder(),
                          prefixIcon: Icon(Icons.search, size: 18),
                        ),
                        onChanged: (v) => setState(() => _query = v),
                      ),
                    ),
                    FilterChip(
                      label: const Text('All groups'),
                      selected: _groupFilter == null,
                      onSelected: (_) => setState(() => _groupFilter = null),
                    ),
                    for (final g in (groups.toList()..sort()))
                      FilterChip(
                        label: Text(g),
                        selected: _groupFilter == g,
                        onSelected: (sel) =>
                            setState(() => _groupFilter = sel ? g : null),
                      ),
                    OutlinedButton.icon(
                      onPressed: () => _editFlow(context),
                      icon: const Icon(Icons.add, size: 18),
                      label: const Text('Flow'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () => _editSuite(context),
                      icon: const Icon(Icons.add, size: 18),
                      label: const Text('Suite'),
                    ),
                    FilledButton.icon(
                      onPressed: () => context.read<UiFlowsCubit>().load(),
                      icon: const Icon(Icons.refresh, size: 18),
                      label: const Text('Refresh'),
                    ),
                  ],
                ),
              ),
              if (state.error != null) ...[
                const SizedBox(height: 8),
                Text(
                  state.error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 10),
              Expanded(
                child: state.loading
                    ? const Center(child: CircularProgressIndicator())
                    : Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          SizedBox(
                            width: 320,
                            child: GlassCard(
                              padding: EdgeInsets.zero,
                              child: Column(
                                children: [
                                  TabBar(
                                    controller: _tabs,
                                    tabs: [
                                      Tab(text: 'Flows (${flows.length})'),
                                      Tab(text: 'Suites (${suites.length})'),
                                    ],
                                  ),
                                  Expanded(
                                    child: TabBarView(
                                      controller: _tabs,
                                      children: [
                                        _FlowsAccordion(
                                          grouped: grouped,
                                          selectedId: _selectedFlowId,
                                          onSelect: (id) => setState(() {
                                            _selectedFlowId = id;
                                            _selectedSuiteId = null;
                                          }),
                                        ),
                                        suites.isEmpty
                                            ? const Center(
                                                child: Text('No suites yet'),
                                              )
                                            : ListView.separated(
                                                itemCount: suites.length,
                                                separatorBuilder: (_, __) =>
                                                    const Divider(height: 1),
                                                itemBuilder: (context, i) {
                                                  final s = suites[i];
                                                  final id = '${s['id'] ?? ''}';
                                                  final profiles = s['profiles'];
                                                  final selected =
                                                      id == _selectedSuiteId;
                                                  return _HoverFlowTile(
                                                    selected: selected,
                                                    title: '${s['label'] ?? id}',
                                                    subtitle:
                                                        'agent=${s['agent_suite'] ?? '—'} · '
                                                        'profiles=${profiles is List ? profiles.length : 0}',
                                                    onTap: () => setState(() {
                                                      _selectedSuiteId = id;
                                                      _selectedFlowId = null;
                                                    }),
                                                  );
                                                },
                                              ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: GlassCard(
                              padding: const EdgeInsets.all(16),
                              child: _tabs.index == 0
                                  ? _FlowDetail(
                                      flow: selectedFlow,
                                      onPlay: selectedFlow == null
                                          ? null
                                          : () => _playFlow(
                                                context,
                                                '${selectedFlow!['id']}',
                                              ),
                                      onEdit: selectedFlow == null
                                          ? null
                                          : () => _editFlow(
                                                context,
                                                existing: selectedFlow,
                                              ),
                                      onReset: selectedFlow == null
                                          ? null
                                          : () => context
                                              .read<UiFlowsCubit>()
                                              .deleteFlow(
                                                '${selectedFlow!['id']}',
                                                reset: true,
                                              ),
                                      onDelete: selectedFlow == null
                                          ? null
                                          : () => context
                                              .read<UiFlowsCubit>()
                                              .deleteFlow(
                                                '${selectedFlow!['id']}',
                                              ),
                                    )
                                  : _SuiteDetail(
                                      suite: selectedSuite,
                                      flowIds: state.flows
                                          .map((f) => '${f['id']}')
                                          .toSet(),
                                      onPlay: selectedSuite == null
                                          ? null
                                          : () => _playSuite(
                                                context,
                                                '${selectedSuite!['id']}',
                                              ),
                                      onEdit: selectedSuite == null
                                          ? null
                                          : () => _editSuite(
                                                context,
                                                existing: selectedSuite,
                                              ),
                                      onReset: selectedSuite == null
                                          ? null
                                          : () => context
                                              .read<UiFlowsCubit>()
                                              .deleteSuite(
                                                '${selectedSuite!['id']}',
                                                reset: true,
                                              ),
                                      onDelete: selectedSuite == null
                                          ? null
                                          : () => context
                                              .read<UiFlowsCubit>()
                                              .deleteSuite(
                                                '${selectedSuite!['id']}',
                                              ),
                                    ),
                            ),
                          ),
                        ],
                      ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _FlowsAccordion extends StatelessWidget {
  const _FlowsAccordion({
    required this.grouped,
    required this.selectedId,
    required this.onSelect,
  });

  final Map<String, List<Map<String, dynamic>>> grouped;
  final String? selectedId;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    if (grouped.isEmpty) {
      return const Center(child: Text('No flows match filters'));
    }
    return ListView(
      children: [
        for (final entry in grouped.entries)
          ExpansionTile(
            initiallyExpanded: true,
            title: Text(
              '${entry.key} (${entry.value.length})',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            children: [
              for (final f in entry.value)
                _HoverFlowTile(
                  selected: '${f['id']}' == selectedId,
                  title: '${f['label'] ?? f['id']}',
                  subtitle:
                      '${f['id']}${_listLen(f['steps']) > 0 ? ' · ${_listLen(f['steps'])} steps' : ''}',
                  onTap: () => onSelect('${f['id']}'),
                ),
            ],
          ),
      ],
    );
  }
}

class _FlowDetail extends StatelessWidget {
  const _FlowDetail({
    required this.flow,
    this.onPlay,
    this.onEdit,
    this.onReset,
    this.onDelete,
  });

  final Map<String, dynamic>? flow;
  final VoidCallback? onPlay;
  final VoidCallback? onEdit;
  final VoidCallback? onReset;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    if (flow == null) {
      return const Center(
        child: Text('Select a flow to see what is set'),
      );
    }
    final f = flow!;
    final id = '${f['id'] ?? ''}';
    final runsAs = '${f['runs_as'] ?? ''}'.trim();
    final group = '${f['group'] ?? ''}'.trim();
    final summary = '${f['summary'] ?? ''}'.trim();
    final steps = _listLen(f['steps']);
    final checks = _listLen(f['verifications']);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                '${f['label'] ?? id}',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ),
            IconButton(
              tooltip: 'Play',
              onPressed: onPlay,
              icon: const Icon(Icons.play_arrow),
            ),
            IconButton(
              tooltip: 'Edit',
              onPressed: onEdit,
              icon: const Icon(Icons.edit_outlined),
            ),
            PopupMenuButton<String>(
              onSelected: (v) {
                if (v == 'reset') onReset?.call();
                if (v == 'delete') onDelete?.call();
              },
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'reset', child: Text('Reset to default')),
                PopupMenuItem(value: 'delete', child: Text('Delete')),
              ],
            ),
          ],
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            _SetChip(label: 'id', value: id, set: id.isNotEmpty),
            _SetChip(label: 'group', value: group.isEmpty ? '—' : group, set: group.isNotEmpty),
            _SetChip(
              label: 'runs_as',
              value: runsAs.isEmpty ? '—' : runsAs,
              set: runsAs.isNotEmpty,
            ),
            _SetChip(label: 'steps', value: '$steps', set: steps > 0),
            _SetChip(label: 'checks', value: '$checks', set: checks > 0),
            _SetChip(
              label: 'summary',
              value: summary.isEmpty ? '—' : 'set',
              set: summary.isNotEmpty,
            ),
          ],
        ),
        const SizedBox(height: 12),
        Text('Summary', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        Text(
          summary.isEmpty ? '(none)' : summary,
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 16),
        Expanded(
          child: Row(
            children: [
              Expanded(
                child: _ItemListPreview(
                  title: 'Steps ($steps)',
                  items: f['steps'],
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _ItemListPreview(
                  title: 'Verifications ($checks)',
                  items: f['verifications'],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SuiteDetail extends StatelessWidget {
  const _SuiteDetail({
    required this.suite,
    required this.flowIds,
    this.onPlay,
    this.onEdit,
    this.onReset,
    this.onDelete,
  });

  final Map<String, dynamic>? suite;
  final Set<String> flowIds;
  final VoidCallback? onPlay;
  final VoidCallback? onEdit;
  final VoidCallback? onReset;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    if (suite == null) {
      return const Center(
        child: Text('Select a suite to see what is set'),
      );
    }
    final s = suite!;
    final id = '${s['id'] ?? ''}';
    final agent = '${s['agent_suite'] ?? ''}'.trim();
    final profiles = s['profiles'];
    final profileList =
        profiles is List ? profiles.map((e) => '$e').toList() : <String>[];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                '${s['label'] ?? id}',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            IconButton(
              tooltip: 'Play',
              onPressed: onPlay,
              icon: const Icon(Icons.play_arrow),
            ),
            IconButton(
              tooltip: 'Edit',
              onPressed: onEdit,
              icon: const Icon(Icons.edit_outlined),
            ),
            PopupMenuButton<String>(
              onSelected: (v) {
                if (v == 'reset') onReset?.call();
                if (v == 'delete') onDelete?.call();
              },
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'reset', child: Text('Reset to default')),
                PopupMenuItem(value: 'delete', child: Text('Delete')),
              ],
            ),
          ],
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            _SetChip(label: 'id', value: id, set: id.isNotEmpty),
            _SetChip(
              label: 'agent_suite',
              value: agent.isEmpty ? '—' : agent,
              set: agent == 'smoke' || agent == 'release_gate',
            ),
            _SetChip(
              label: 'profiles',
              value: '${profileList.length}',
              set: profileList.isNotEmpty,
            ),
          ],
        ),
        const SizedBox(height: 16),
        Text('Profiles', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        if (profileList.isEmpty)
          const Text('(none)')
        else
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final p in profileList)
                Chip(
                  visualDensity: VisualDensity.compact,
                  avatar: Icon(
                    flowIds.contains(p) ? Icons.check_circle : Icons.warning,
                    size: 16,
                    color: flowIds.contains(p)
                        ? AppColors.primary
                        : Theme.of(context).colorScheme.error,
                  ),
                  label: Text(p),
                ),
            ],
          ),
      ],
    );
  }
}

class _SetChip extends StatelessWidget {
  const _SetChip({
    required this.label,
    required this.value,
    required this.set,
  });

  final String label;
  final String value;
  final bool set;

  @override
  Widget build(BuildContext context) {
    return Chip(
      visualDensity: VisualDensity.compact,
      avatar: Icon(
        set ? Icons.check : Icons.remove,
        size: 16,
        color: set ? AppColors.primary : Theme.of(context).disabledColor,
      ),
      label: Text('$label: $value'),
      backgroundColor: set
          ? AppColors.primary.withValues(alpha: 0.12)
          : Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
    );
  }
}

class _ItemListPreview extends StatelessWidget {
  const _ItemListPreview({required this.title, required this.items});

  final String title;
  final dynamic items;

  @override
  Widget build(BuildContext context) {
    final list = items is List ? List<dynamic>.from(items as List) : const <dynamic>[];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 6),
        Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
            decoration: BoxDecoration(
              color: Theme.of(context)
                  .colorScheme
                  .surfaceContainerHighest
                  .withValues(alpha: 0.35),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: Theme.of(context).dividerColor.withValues(alpha: 0.4),
              ),
            ),
            child: list.isEmpty
                ? Center(
                    child: Text(
                      '(none)',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppColors.textSecondaryDark,
                          ),
                    ),
                  )
                : ListView.separated(
                    itemCount: list.length,
                    separatorBuilder: (_, __) => Divider(
                      height: 12,
                      color: Theme.of(context).dividerColor.withValues(alpha: 0.25),
                    ),
                    itemBuilder: (context, i) {
                      final raw = list[i];
                      final text = raw is String
                          ? raw
                          : const JsonEncoder.withIndent('  ').convert(raw);
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 22,
                            height: 22,
                            alignment: Alignment.center,
                            decoration: BoxDecoration(
                              color: AppColors.primary.withValues(alpha: 0.18),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              '${i + 1}',
                              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                    fontWeight: FontWeight.w700,
                                    color: AppColors.primary,
                                  ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: SelectableText(
                              text,
                              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                    height: 1.35,
                                  ),
                            ),
                          ),
                        ],
                      );
                    },
                  ),
          ),
        ),
      ],
    );
  }
}

class _HoverFlowTile extends StatefulWidget {
  const _HoverFlowTile({
    required this.title,
    required this.subtitle,
    required this.selected,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final bool selected;
  final VoidCallback onTap;

  @override
  State<_HoverFlowTile> createState() => _HoverFlowTileState();
}

class _HoverFlowTileState extends State<_HoverFlowTile> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final selected = widget.selected;
    final bg = selected
        ? AppColors.primary.withValues(alpha: 0.16)
        : _hover
            ? AppColors.primary.withValues(alpha: 0.08)
            : Colors.transparent;
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 140),
        margin: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(8),
          border: Border(
            left: BorderSide(
              color: selected ? AppColors.primary : Colors.transparent,
              width: 3,
            ),
          ),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: widget.onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  widget.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
                const SizedBox(height: 2),
                Text(
                  widget.subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppColors.textSecondaryDark,
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
