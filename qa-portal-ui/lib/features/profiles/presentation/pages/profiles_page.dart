import 'package:am_design_system/am_design_system.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/json_lists.dart';
import '../../../execute/data/execute_repository.dart';
import '../../data/profiles_repository.dart';

const _durationPresets = ['30s', '1m', '5m', '10m'];

class ProfilesPage extends StatelessWidget {
  const ProfilesPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => ProfilesCubit(
        getIt<ProfilesRepository>(),
        getIt<ExecuteRepository>(),
        getIt<ApiClient>(),
      )..load(),
      child: const _ProfilesView(),
    );
  }
}

class ProfilesState extends Equatable {
  const ProfilesState({
    this.loading = false,
    this.items = const [],
    this.selected,
    this.error,
    this.saving = false,
    this.running = false,
    this.targetHint,
  });

  final bool loading;
  final List<Map<String, dynamic>> items;
  final Map<String, dynamic>? selected;
  final String? error;
  final bool saving;
  final bool running;
  final String? targetHint;

  ProfilesState copyWith({
    bool? loading,
    List<Map<String, dynamic>>? items,
    Map<String, dynamic>? selected,
    String? error,
    bool? saving,
    bool? running,
    String? targetHint,
    bool clearSelected = false,
    bool clearTargetHint = false,
  }) {
    return ProfilesState(
      loading: loading ?? this.loading,
      items: items ?? this.items,
      selected: clearSelected ? null : (selected ?? this.selected),
      error: error,
      saving: saving ?? this.saving,
      running: running ?? this.running,
      targetHint: clearTargetHint ? null : (targetHint ?? this.targetHint),
    );
  }

  @override
  List<Object?> get props =>
      [loading, items, selected, error, saving, running, targetHint];
}

class ProfilesCubit extends Cubit<ProfilesState> {
  ProfilesCubit(this._repo, this._execute, this._api) : super(const ProfilesState());

  final ProfilesRepository _repo;
  final ExecuteRepository _execute;
  final ApiClient _api;

  Future<void> load() async {
    emit(state.copyWith(loading: true, error: null));
    try {
      final items = await _repo.listConfigs();
      emit(state.copyWith(loading: false, items: items));
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }

  Future<void> select(String id) async {
    emit(state.copyWith(loading: true, error: null, clearTargetHint: true));
    try {
      final cfg = await _repo.getConfig(id);
      emit(state.copyWith(loading: false, selected: cfg));
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }

  void newDraft() {
    emit(
      state.copyWith(
        clearTargetHint: true,
        selected: {
          'name': 'new-profile',
          'service': 'am-core-services',
          'environment': 'dev',
          'test_type': 'k6',
          'audience': 'developer',
          'vus': 1,
          'iterations': 1,
          'duration': '30s',
        },
      ),
    );
  }

  void patchSelected(String key, dynamic value) {
    final cur = Map<String, dynamic>.from(state.selected ?? {});
    cur[key] = value;
    emit(state.copyWith(selected: cur));
  }

  Future<void> fillTarget() async {
    final sel = state.selected;
    if (sel == null) return;
    final service = '${sel['service'] ?? ''}'.trim();
    final environment = '${sel['environment'] ?? 'dev'}'.trim();
    if (service.isEmpty) {
      emit(state.copyWith(targetHint: 'Set service first'));
      return;
    }
    try {
      final res = await _api.get(
        '/api/catalog/$service/target',
        query: {'environment': environment},
      );
      final data = asMap(res.data);
      final url = '${data['target_url'] ?? ''}'.trim();
      if (url.isEmpty) {
        emit(state.copyWith(targetHint: 'No target for $service/$environment'));
        return;
      }
      patchSelected('target_url', url.replaceAll(RegExp(r'/$'), ''));
      emit(
        state.copyWith(
          targetHint: 'Filled from ${data['source'] ?? 'catalog'}',
        ),
      );
    } catch (e) {
      emit(state.copyWith(targetHint: e.toString()));
    }
  }

  Future<String?> runSelected() async {
    final sel = state.selected;
    if (sel == null) return null;
    final id = sel['id']?.toString();
    if (id == null || id.isEmpty) return null;

    emit(state.copyWith(running: true, error: null));
    try {
      var vus = sel['vus'];
      if (vus is String) vus = int.tryParse(vus) ?? 1;
      var calls = sel['iterations'];
      if (calls is String) calls = int.tryParse(calls) ?? 1;

      final apiIdsRaw = sel['selected_api_ids'];
      List<String>? apiIds;
      if (apiIdsRaw is List) {
        apiIds = apiIdsRaw.map((e) => '$e').where((e) => e.isNotEmpty).toList();
      } else if (apiIdsRaw is String && apiIdsRaw.trim().isNotEmpty) {
        apiIds = apiIdsRaw
            .split(',')
            .map((e) => e.trim())
            .where((e) => e.isNotEmpty)
            .toList();
      }

      final out = await _execute.execute(
        configId: id,
        testType: '${sel['test_type'] ?? 'k6'}',
        vus: vus is int ? vus : 1,
        calls: calls is int ? calls : 1,
        uiProfile: sel['ui_profile']?.toString(),
        uiSuite: sel['ui_suite']?.toString(),
        apiIds: apiIds,
        openapiVersion: sel['openapi_version']?.toString(),
      );
      emit(state.copyWith(running: false));
      return '${out['id'] ?? out['run_id'] ?? ''}';
    } catch (e) {
      emit(state.copyWith(running: false, error: e.toString()));
      return null;
    }
  }

  Future<void> save() async {
    final sel = state.selected;
    if (sel == null) return;
    emit(state.copyWith(saving: true, error: null));
    try {
      final body = Map<String, dynamic>.from(sel);
      for (final k in ['vus', 'iterations']) {
        final v = body[k];
        if (v is String) {
          final n = int.tryParse(v);
          if (n != null) body[k] = n;
        }
      }
      final apiIds = body['selected_api_ids'];
      if (apiIds is String) {
        body['selected_api_ids'] = apiIds
            .split(',')
            .map((e) => e.trim())
            .where((e) => e.isNotEmpty)
            .toList();
      }
      final id = body['id']?.toString();
      if (id == null || id.isEmpty) {
        await _repo.createConfig(body);
      } else {
        await _repo.updateConfig(id, body);
      }
      await load();
      emit(state.copyWith(saving: false));
    } catch (e) {
      emit(state.copyWith(saving: false, error: e.toString()));
    }
  }

  Future<void> deleteSelected() async {
    final id = state.selected?['id']?.toString();
    if (id == null || id.isEmpty) return;
    await _repo.deleteConfig(id);
    emit(state.copyWith(clearSelected: true));
    await load();
  }
}

String _apiIdsText(Map<String, dynamic>? sel) {
  final raw = sel?['selected_api_ids'];
  if (raw is List) {
    return raw.map((e) => '$e').where((e) => e.isNotEmpty).join(', ');
  }
  return raw?.toString() ?? '';
}

class _ProfilesView extends StatefulWidget {
  const _ProfilesView();

  @override
  State<_ProfilesView> createState() => _ProfilesViewState();
}

class _ProfilesViewState extends State<_ProfilesView> {
  String _query = '';
  String _serviceFilter = '';
  String _audienceFilter = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final configId = GoRouterState.of(context).uri.queryParameters['config'];
      if (configId != null && configId.isNotEmpty) {
        context.read<ProfilesCubit>().select(configId);
      }
    });
  }

  List<Map<String, dynamic>> _filtered(List<Map<String, dynamic>> items) {
    final q = _query.trim().toLowerCase();
    return items.where((c) {
      if (_serviceFilter.isNotEmpty && '${c['service'] ?? ''}' != _serviceFilter) {
        return false;
      }
      if (_audienceFilter.isNotEmpty && '${c['audience'] ?? ''}' != _audienceFilter) {
        return false;
      }
      if (q.isEmpty) return true;
      final hay =
          '${c['id']} ${c['name']} ${c['service']} ${c['environment']} ${c['test_type']}'
              .toLowerCase();
      return hay.contains(q);
    }).toList();
  }

  Future<void> _confirmDelete(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete profile?'),
        content: const Text('This cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete')),
        ],
      ),
    );
    if (ok == true && context.mounted) {
      await context.read<ProfilesCubit>().deleteSelected();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: BlocBuilder<ProfilesCubit, ProfilesState>(
        builder: (context, state) {
          final items = _filtered(state.items);
          final services = {
            for (final c in state.items) '${c['service'] ?? ''}',
          }..remove('');
          return Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SizedBox(
                width: 320,
                child: GlassCard(
                  padding: EdgeInsets.zero,
                  child: Column(
                    children: [
                      Padding(
                        padding: const EdgeInsets.all(8),
                        child: Column(
                          children: [
                            Row(
                              children: [
                                Text(
                                  'Profiles',
                                  style: Theme.of(context).textTheme.titleMedium,
                                ),
                                const Spacer(),
                                IconButton(
                                  onPressed: () =>
                                      context.read<ProfilesCubit>().newDraft(),
                                  icon: const Icon(Icons.add),
                                  tooltip: 'New',
                                ),
                                IconButton(
                                  onPressed: () =>
                                      context.read<ProfilesCubit>().load(),
                                  icon: const Icon(Icons.refresh),
                                ),
                              ],
                            ),
                            TextField(
                              decoration: const InputDecoration(
                                labelText: 'Search',
                                isDense: true,
                                border: OutlineInputBorder(),
                                prefixIcon: Icon(Icons.search, size: 18),
                              ),
                              onChanged: (v) => setState(() => _query = v),
                            ),
                            const SizedBox(height: 6),
                            Row(
                              children: [
                                Expanded(
                                  child: DropdownButtonFormField<String>(
                                    initialValue: _serviceFilter,
                                    isExpanded: true,
                                    decoration: const InputDecoration(
                                      labelText: 'Service',
                                      isDense: true,
                                      border: OutlineInputBorder(),
                                    ),
                                    items: [
                                      const DropdownMenuItem(
                                        value: '',
                                        child: Text('Any'),
                                      ),
                                      for (final s in (services.toList()..sort()))
                                        DropdownMenuItem(value: s, child: Text(s)),
                                    ],
                                    onChanged: (v) =>
                                        setState(() => _serviceFilter = v ?? ''),
                                  ),
                                ),
                                const SizedBox(width: 6),
                                Expanded(
                                  child: DropdownButtonFormField<String>(
                                    initialValue: _audienceFilter,
                                    isExpanded: true,
                                    decoration: const InputDecoration(
                                      labelText: 'Audience',
                                      isDense: true,
                                      border: OutlineInputBorder(),
                                    ),
                                    items: const [
                                      DropdownMenuItem(value: '', child: Text('Any')),
                                      DropdownMenuItem(
                                        value: 'developer',
                                        child: Text('developer'),
                                      ),
                                      DropdownMenuItem(
                                        value: 'agent',
                                        child: Text('agent'),
                                      ),
                                      DropdownMenuItem(value: 'ci', child: Text('ci')),
                                      DropdownMenuItem(
                                        value: 'shared',
                                        child: Text('shared'),
                                      ),
                                    ],
                                    onChanged: (v) =>
                                        setState(() => _audienceFilter = v ?? ''),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      const Divider(height: 1),
                      Expanded(
                        child: state.loading && state.items.isEmpty
                            ? const Center(child: CircularProgressIndicator())
                            : items.isEmpty
                                ? const Center(child: Text('No profiles match'))
                                : ListView.builder(
                                    padding: const EdgeInsets.symmetric(vertical: 4),
                                    itemCount: items.length,
                                    itemBuilder: (context, i) {
                                      final c = items[i];
                                      final id = '${c['id'] ?? ''}';
                                      final selected =
                                          id == '${state.selected?['id'] ?? ''}';
                                      return _HoverListTile(
                                        selected: selected,
                                        title: '${c['name'] ?? id}',
                                        subtitle:
                                            '${c['service'] ?? ''} · ${c['environment'] ?? ''} · ${c['test_type'] ?? ''}',
                                        onTap: () =>
                                            context.read<ProfilesCubit>().select(id),
                                      );
                                    },
                                  ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: state.selected == null
                    ? GlassCard(
                        child: Center(
                          child: Text(
                            'Select or create a profile',
                            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                                  color: AppColors.textSecondaryDark,
                                ),
                          ),
                        ),
                      )
                    : GlassCard(
                        padding: EdgeInsets.zero,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Expanded(
                              child: ListView(
                                padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                                children: [
                                  Text(
                                    state.selected!['id'] == null
                                        ? 'New profile'
                                        : 'Edit profile',
                                    style: Theme.of(context)
                                        .textTheme
                                        .headlineSmall
                                        ?.copyWith(fontWeight: FontWeight.w700),
                                  ),
                                  if (state.selected!['id'] != null) ...[
                                    const SizedBox(height: 4),
                                    SelectableText(
                                      '${state.selected!['id']}',
                                      style: Theme.of(context)
                                          .textTheme
                                          .bodySmall
                                          ?.copyWith(
                                            fontFamily: 'monospace',
                                            color: AppColors.textSecondaryDark,
                                          ),
                                    ),
                                  ],
                                  const SizedBox(height: 16),
                                  _sectionTitle(context, 'Identity'),
                                  _field(context, 'name', 'Name'),
                                  _field(context, 'service', 'Service'),
                                  _dropdown(
                                    context,
                                    'environment',
                                    'Environment',
                                    const ['dev', 'preprod', 'prod'],
                                  ),
                                  _dropdown(
                                    context,
                                    'test_type',
                                    'Test type',
                                    const ['k6', 'playwright', 'mixed'],
                                  ),
                                  _dropdown(
                                    context,
                                    'audience',
                                    'Audience',
                                    const ['developer', 'agent', 'ci', 'shared'],
                                  ),
                                  const SizedBox(height: 8),
                                  _sectionTitle(context, 'Target'),
                                  Row(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Expanded(
                                        child: _field(
                                          context,
                                          'target_url',
                                          'Target URL (optional)',
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Padding(
                                        padding: const EdgeInsets.only(top: 8),
                                        child: OutlinedButton(
                                          onPressed: () => context
                                              .read<ProfilesCubit>()
                                              .fillTarget(),
                                          child: const Text('Fill target'),
                                        ),
                                      ),
                                    ],
                                  ),
                                  if (state.targetHint != null)
                                    Padding(
                                      padding: const EdgeInsets.only(bottom: 10),
                                      child: Text(
                                        state.targetHint!,
                                        style: Theme.of(context).textTheme.bodySmall,
                                      ),
                                    ),
                                  _field(
                                    context,
                                    'openapi_version',
                                    'OpenAPI version (optional)',
                                  ),
                                  _field(
                                    context,
                                    'selected_api_ids',
                                    'API ids (comma-separated, optional)',
                                    initial: _apiIdsText(state.selected),
                                  ),
                                  const SizedBox(height: 8),
                                  _sectionTitle(context, 'Load / bench'),
                                  _field(context, 'vus', 'VUs'),
                                  _field(context, 'iterations', 'Iterations / calls'),
                                  _durationRow(context, state),
                                  const SizedBox(height: 8),
                                  _sectionTitle(context, 'UI'),
                                  _field(context, 'ui_profile', 'UI profile (optional)'),
                                  _field(context, 'ui_suite', 'UI suite (optional)'),
                                  if (state.error != null)
                                    Text(
                                      state.error!,
                                      style: TextStyle(
                                        color: Theme.of(context).colorScheme.error,
                                      ),
                                    ),
                                ],
                              ),
                            ),
                            Material(
                              color: Theme.of(context)
                                  .colorScheme
                                  .surfaceContainerHighest
                                  .withValues(alpha: 0.45),
                              child: Padding(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                  vertical: 10,
                                ),
                                child: Wrap(
                                  spacing: 8,
                                  runSpacing: 8,
                                  children: [
                                    FilledButton(
                                      onPressed: state.saving
                                          ? null
                                          : () =>
                                              context.read<ProfilesCubit>().save(),
                                      child: Text(state.saving ? 'Saving…' : 'Save'),
                                    ),
                                    if (state.selected!['id'] != null)
                                      OutlinedButton(
                                        onPressed: () => _confirmDelete(context),
                                        child: const Text('Delete'),
                                      ),
                                    if (state.selected!['id'] != null)
                                      FilledButton.icon(
                                        onPressed: state.running
                                            ? null
                                            : () async {
                                                final runId = await context
                                                    .read<ProfilesCubit>()
                                                    .runSelected();
                                                if (runId != null &&
                                                    runId.isNotEmpty &&
                                                    context.mounted) {
                                                  context.go('/runs/$runId');
                                                }
                                              },
                                        icon: state.running
                                            ? const SizedBox(
                                                width: 16,
                                                height: 16,
                                                child: CircularProgressIndicator(
                                                  strokeWidth: 2,
                                                ),
                                              )
                                            : const Icon(Icons.play_arrow, size: 18),
                                        label: const Text('Run with this profile'),
                                      ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _sectionTitle(BuildContext context, String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w700,
              letterSpacing: 0.2,
            ),
      ),
    );
  }

  Widget _field(
    BuildContext context,
    String key,
    String label, {
    String? initial,
  }) {
    final cubit = context.read<ProfilesCubit>();
    final val = initial ?? '${cubit.state.selected?[key] ?? ''}';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextFormField(
        key: ValueKey('$key-$val-${cubit.state.selected?['id']}'),
        initialValue: val,
        style: Theme.of(context).textTheme.bodyMedium,
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          border: const OutlineInputBorder(),
        ),
        onChanged: (v) => cubit.patchSelected(key, v),
      ),
    );
  }

  Widget _dropdown(
    BuildContext context,
    String key,
    String label,
    List<String> options,
  ) {
    final cubit = context.read<ProfilesCubit>();
    final raw = '${cubit.state.selected?[key] ?? options.first}';
    final value = options.contains(raw) ? raw : options.first;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DropdownButtonFormField<String>(
        key: ValueKey('$key-$value-${cubit.state.selected?['id']}'),
        initialValue: value,
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          border: const OutlineInputBorder(),
        ),
        items: [
          for (final o in options)
            DropdownMenuItem(value: o, child: Text(o)),
        ],
        onChanged: (v) {
          if (v != null) cubit.patchSelected(key, v);
        },
      ),
    );
  }

  Widget _durationRow(BuildContext context, ProfilesState state) {
    final cubit = context.read<ProfilesCubit>();
    final duration = '${state.selected?['duration'] ?? ''}';
    final preset = _durationPresets.contains(duration) ? duration : null;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Duration', style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final p in _durationPresets)
                AnimatedScale(
                  scale: preset == p ? 1.04 : 1.0,
                  duration: const Duration(milliseconds: 140),
                  child: ChoiceChip(
                    label: Text(p),
                    selected: preset == p,
                    onSelected: (_) => cubit.patchSelected('duration', p),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          TextFormField(
            key: ValueKey('duration-$duration-${state.selected?['id']}'),
            initialValue: duration,
            decoration: const InputDecoration(
              labelText: 'Custom duration (e.g. 30s, 2m)',
              isDense: true,
              border: OutlineInputBorder(),
            ),
            onChanged: (v) => cubit.patchSelected('duration', v),
          ),
        ],
      ),
    );
  }
}

class _HoverListTile extends StatefulWidget {
  const _HoverListTile({
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
  State<_HoverListTile> createState() => _HoverListTileState();
}

class _HoverListTileState extends State<_HoverListTile> {
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
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
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
