part of 'profiles_page.dart';

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
      if (getIt.isRegistered<SpecsProfileDefaults>()) {
        // ignore: unawaited_futures
        getIt<SpecsProfileDefaults>().pushFromConfig(cfg);
      }
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

