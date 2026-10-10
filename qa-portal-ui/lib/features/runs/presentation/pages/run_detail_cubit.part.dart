part of 'run_detail_page.dart';

class _RunDetailState {
  const _RunDetailState({
    this.loading = true,
    this.actionBusy = false,
    this.run = const {},
    this.artifacts = const [],
    this.apis = const [],
    this.traces = const [],
    this.selectedTrace,
    this.selectedTraceApiId,
    this.failedOnly = false,
    this.baseline,
    this.error,
  });

  final bool loading;
  final bool actionBusy;
  final Map<String, dynamic> run;
  final List<Map<String, dynamic>> artifacts;
  final List<Map<String, dynamic>> apis;
  final List<Map<String, dynamic>> traces;
  final Map<String, dynamic>? selectedTrace;
  final String? selectedTraceApiId;
  final bool failedOnly;
  final Map<String, dynamic>? baseline;
  final String? error;

  _RunDetailState copyWith({
    bool? loading,
    bool? actionBusy,
    Map<String, dynamic>? run,
    List<Map<String, dynamic>>? artifacts,
    List<Map<String, dynamic>>? apis,
    List<Map<String, dynamic>>? traces,
    Map<String, dynamic>? selectedTrace,
    String? selectedTraceApiId,
    bool? failedOnly,
    Map<String, dynamic>? baseline,
    String? error,
    bool clearTrace = false,
    bool clearTraceApiId = false,
  }) {
    return _RunDetailState(
      loading: loading ?? this.loading,
      actionBusy: actionBusy ?? this.actionBusy,
      run: run ?? this.run,
      artifacts: artifacts ?? this.artifacts,
      apis: apis ?? this.apis,
      traces: traces ?? this.traces,
      selectedTrace: clearTrace ? null : (selectedTrace ?? this.selectedTrace),
      selectedTraceApiId:
          clearTraceApiId ? null : (selectedTraceApiId ?? this.selectedTraceApiId),
      failedOnly: failedOnly ?? this.failedOnly,
      baseline: baseline ?? this.baseline,
      error: error,
    );
  }
}

int _intFrom(dynamic v, int fallback) {
  if (v is int) return v;
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? fallback;
  return fallback;
}

Map<String, dynamic> _runParams(Map<String, dynamic> run) {
  final params = run['params'];
  return params is Map ? Map<String, dynamic>.from(params) : const {};
}

String? _runIdFrom(Map<String, dynamic> out) {
  final id = '${out['id'] ?? out['run_id'] ?? ''}';
  return id.isEmpty ? null : id;
}

class _RunDetailCubit extends Cubit<_RunDetailState> {
  _RunDetailCubit(this._repo, this.runId) : super(const _RunDetailState());

  final RunsRepository _repo;
  final String runId;

  Future<Map<String, dynamic>> loadObsLogs() => _repo.obsLogs(runId);

  Future<void> load() async {
    emit(state.copyWith(loading: true, error: null));
    try {
      final run = await _repo.getRun(runId);
      List<Map<String, dynamic>> arts = const [];
      List<Map<String, dynamic>> apis = const [];
      List<Map<String, dynamic>> traces = const [];
      Map<String, dynamic>? baseline;
      try {
        arts = await _repo.artifacts(runId);
      } catch (_) {}
      try {
        apis = await _repo.runApis(runId, failedOnly: state.failedOnly);
      } catch (_) {}
      try {
        traces = await _repo.traces(runId, failedOnly: state.failedOnly);
      } catch (_) {}
      try {
        baseline = await _repo.baseline(runId);
      } catch (_) {}
      emit(
        state.copyWith(
          loading: false,
          run: run,
          artifacts: arts,
          apis: apis,
          traces: traces,
          baseline: baseline,
        ),
      );
      final status = '${run['status'] ?? ''}';
      if (status == 'running' || status == 'pending') {
        Future<void>.delayed(const Duration(seconds: 2), () {
          if (!isClosed) load();
        });
      }
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }

  Future<void> setFailedOnly(bool v) async {
    emit(state.copyWith(failedOnly: v));
    await load();
  }

  Future<void> openTrace(Map<String, dynamic> row) async {
    final apiId = '${row['api_id'] ?? row['id'] ?? ''}';
    final index = row['index'];
    try {
      Map<String, dynamic> detail;
      if (index is int) {
        detail = await _repo.traceAt(runId, index);
      } else if (apiId.isNotEmpty) {
        detail = await _repo.apiTrace(runId, apiId);
      } else {
        detail = row;
      }
      final trace = detail['trace'] is Map
          ? Map<String, dynamic>.from(detail['trace'] as Map)
          : detail;
      final traceApiId = '${trace['api_id'] ?? apiId}';
      emit(
        state.copyWith(
          selectedTrace: trace,
          selectedTraceApiId: traceApiId.isEmpty ? null : traceApiId,
        ),
      );
    } catch (e) {
      emit(state.copyWith(error: e.toString()));
    }
  }

  Future<void> stop() async {
    try {
      await _repo.stopRun(runId);
      await load();
    } catch (e) {
      emit(state.copyWith(error: e.toString()));
    }
  }

  Future<String?> rerun() async {
    final run = state.run;
    final configId = '${run['config_id'] ?? ''}';
    if (configId.isEmpty) {
      emit(state.copyWith(error: 'Run has no config_id'));
      return null;
    }
    final params = _runParams(run);
    final testType = '${run['test_type'] ?? 'k6'}';
    final vus = _intFrom(params['vus'] ?? run['vus'], 1);
    final calls = _intFrom(params['iterations'] ?? params['calls'] ?? run['iterations'], 1);
    emit(state.copyWith(actionBusy: true, error: null));
    try {
      final out = await _repo.execute(
        configId: configId,
        testType: testType,
        vus: vus,
        calls: calls,
        profile: 'load',
      );
      emit(state.copyWith(actionBusy: false));
      return _runIdFrom(out);
    } catch (e) {
      emit(state.copyWith(actionBusy: false, error: e.toString()));
      return null;
    }
  }

  Future<String?> debugRun() async {
    final run = state.run;
    final configId = '${run['config_id'] ?? ''}';
    if (configId.isEmpty) {
      emit(state.copyWith(error: 'Run has no config_id'));
      return null;
    }
    final testType = '${run['test_type'] ?? 'k6'}';
    emit(state.copyWith(actionBusy: true, error: null));
    try {
      final out = await _repo.execute(
        configId: configId,
        testType: testType,
        vus: 1,
        calls: 1,
        profile: 'debug',
      );
      emit(state.copyWith(actionBusy: false));
      return _runIdFrom(out);
    } catch (e) {
      emit(state.copyWith(actionBusy: false, error: e.toString()));
      return null;
    }
  }

  Future<Map<String, dynamic>?> saveAsConfig(String name) async {
    emit(state.copyWith(actionBusy: true, error: null));
    try {
      final out = await _repo.saveAsConfig(runId, name: name);
      emit(state.copyWith(actionBusy: false));
      return out;
    } catch (e) {
      emit(state.copyWith(actionBusy: false, error: e.toString()));
      return null;
    }
  }

  Future<Map<String, dynamic>?> exportRun() async {
    emit(state.copyWith(actionBusy: true, error: null));
    try {
      final out = await _repo.exportRun(runId);
      emit(state.copyWith(actionBusy: false));
      return out;
    } catch (e) {
      emit(state.copyWith(actionBusy: false, error: e.toString()));
      return null;
    }
  }

  Future<Map<String, dynamic>?> savePayload(String apiId, {String? name}) async {
    emit(state.copyWith(actionBusy: true, error: null));
    try {
      final out = await _repo.savePayload(runId, apiId, name: name);
      emit(state.copyWith(actionBusy: false));
      return out;
    } catch (e) {
      emit(state.copyWith(actionBusy: false, error: e.toString()));
      return null;
    }
  }
}

