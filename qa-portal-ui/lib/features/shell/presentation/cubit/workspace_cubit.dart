import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/config/connection_presets.dart';
import '../../../../core/config/portal_runtime.dart';
import '../../../../core/di/injection.dart';
import '../../data/workspace_store.dart';

class WorkspaceCubitState {
  const WorkspaceCubitState({
    this.workspaces = const [],
    this.active,
    this.loading = true,
  });

  final List<PortalWorkspace> workspaces;
  final PortalWorkspace? active;
  final bool loading;

  WorkspaceCubitState copyWith({
    List<PortalWorkspace>? workspaces,
    PortalWorkspace? active,
    bool? loading,
    bool clearActive = false,
  }) {
    return WorkspaceCubitState(
      workspaces: workspaces ?? this.workspaces,
      active: clearActive ? null : (active ?? this.active),
      loading: loading ?? this.loading,
    );
  }
}

class WorkspaceCubit extends Cubit<WorkspaceCubitState> {
  WorkspaceCubit(this._store) : super(const WorkspaceCubitState());

  final WorkspaceStore _store;

  void _applyConnection(PortalWorkspace? ws) {
    if (ws == null || !getIt.isRegistered<PortalRuntime>()) return;
    final runtime = getIt<PortalRuntime>();
    final hasExplicit = (ws.apiBase ?? '').trim().isNotEmpty ||
        (ws.connectionId ?? '').trim().isNotEmpty;
    // Explicit Environments choice overrides bake-time API_BASE.
    // Otherwise leave Dio on bake-time (localhost vs Contabo dig from npm script).
    if (!hasExplicit) return;
    runtime.setApiBase(ws.resolvedApiBase(fallback: runtime.apiBase));
  }

  Future<void> load() async {
    emit(state.copyWith(loading: true));
    final all = await _store.loadAll();
    final active = await _store.active() ?? (all.isNotEmpty ? all.first : null);
    _applyConnection(active);
    emit(
      WorkspaceCubitState(
        workspaces: all,
        active: active,
        loading: false,
      ),
    );
  }

  Future<void> select(String id) async {
    await _store.setActiveId(id);
    final all = await _store.loadAll();
    final active = all.cast<PortalWorkspace?>().firstWhere(
          (w) => w?.id == id,
          orElse: () => all.isNotEmpty ? all.first : null,
        );
    _applyConnection(active);
    emit(state.copyWith(workspaces: all, active: active));
  }

  Future<void> saveActive({
    String? name,
    String? environment,
    String? defaultService,
    String? connectionId,
    String? apiBase,
    Map<String, String>? variables,
    bool clearService = false,
  }) async {
    final cur = state.active;
    if (cur == null) return;
    final next = cur.copyWith(
      name: name,
      environment: environment,
      defaultService: defaultService,
      connectionId: connectionId,
      apiBase: apiBase,
      variables: variables,
      clearService: clearService,
    );
    await _store.upsert(next);
    await load();
  }

  Future<PortalWorkspace> create({
    required String name,
    required String environment,
    String? defaultService,
    String? connectionId,
    String? apiBase,
    Map<String, String>? variables,
  }) async {
    final preset = ConnectionPreset.byId(connectionId) ?? ConnectionPreset.local;
    final ws = PortalWorkspace(
      id: 'ws_${DateTime.now().millisecondsSinceEpoch}',
      name: name,
      environment: environment,
      defaultService: defaultService,
      connectionId: connectionId ?? preset.id,
      apiBase: apiBase ?? preset.apiBase,
      variables: variables ?? const {},
    );
    await _store.upsert(ws);
    await _store.setActiveId(ws.id);
    await load();
    return ws;
  }
}
