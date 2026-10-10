part of 'execute_bar.dart';

class _ExecuteState {
  const _ExecuteState({
    this.configs = const [],
    this.flowIds = const [],
    this.suiteIds = const [],
    this.catalogApis = const [],
    this.selectedApiIds = const {},
    this.openapiVersions = const [],
    this.configId,
    this.testType = 'k6',
    this.vus = 1,
    this.calls = 1,
    this.runProfile = 'debug',
    this.reportFormats = const ['html', 'json'],
    this.openapiVersion,
    this.payloadSetVersion,
    this.configEnvironment,
    this.configService,
    this.preset = 'custom',
    this.uiProfile,
    this.uiSuite,
    this.lastRunId,
    this.busy = false,
    this.message,
  });

  final List<Map<String, dynamic>> configs;
  final List<String> flowIds;
  final List<String> suiteIds;
  final List<Map<String, dynamic>> catalogApis;
  final Set<String> selectedApiIds;
  final List<String> openapiVersions;
  final String? configId;
  final String testType;
  final int vus;
  final int calls;
  final String runProfile;
  final List<String> reportFormats;
  final String? openapiVersion;
  /// Dataset / payload-set version from the selected profile (for Execute + Specs).
  final String? payloadSetVersion;
  final String? configEnvironment;
  final String? configService;
  final String preset;
  final String? uiProfile;
  final String? uiSuite;
  final String? lastRunId;
  final bool busy;
  final String? message;

  Map<String, dynamic>? get selectedConfig {
    for (final c in configs) {
      if ('${c['id']}' == configId) return c;
    }
    return null;
  }

  String get audience => '${selectedConfig?['audience'] ?? 'developer'}';

  bool get audienceLocked => audience != 'developer' && audience.isNotEmpty;

  _ExecuteState copyWith({
    List<Map<String, dynamic>>? configs,
    List<String>? flowIds,
    List<String>? suiteIds,
    List<Map<String, dynamic>>? catalogApis,
    Set<String>? selectedApiIds,
    List<String>? openapiVersions,
    String? configId,
    String? testType,
    int? vus,
    int? calls,
    String? runProfile,
    List<String>? reportFormats,
    String? openapiVersion,
    String? payloadSetVersion,
    String? configEnvironment,
    String? configService,
    String? preset,
    String? uiProfile,
    String? uiSuite,
    String? lastRunId,
    bool? busy,
    String? message,
    bool clearUiProfile = false,
    bool clearUiSuite = false,
    bool clearLastRun = false,
    bool clearOpenapiVersion = false,
    bool clearPayloadSetVersion = false,
    bool clearConfigEnvironment = false,
    bool clearConfigService = false,
  }) {
    return _ExecuteState(
      configs: configs ?? this.configs,
      flowIds: flowIds ?? this.flowIds,
      suiteIds: suiteIds ?? this.suiteIds,
      catalogApis: catalogApis ?? this.catalogApis,
      selectedApiIds: selectedApiIds ?? this.selectedApiIds,
      openapiVersions: openapiVersions ?? this.openapiVersions,
      configId: configId ?? this.configId,
      testType: testType ?? this.testType,
      vus: vus ?? this.vus,
      calls: calls ?? this.calls,
      runProfile: runProfile ?? this.runProfile,
      reportFormats: reportFormats ?? this.reportFormats,
      openapiVersion:
          clearOpenapiVersion ? null : (openapiVersion ?? this.openapiVersion),
      payloadSetVersion: clearPayloadSetVersion
          ? null
          : (payloadSetVersion ?? this.payloadSetVersion),
      configEnvironment: clearConfigEnvironment
          ? null
          : (configEnvironment ?? this.configEnvironment),
      configService:
          clearConfigService ? null : (configService ?? this.configService),
      preset: preset ?? this.preset,
      uiProfile: clearUiProfile ? null : (uiProfile ?? this.uiProfile),
      uiSuite: clearUiSuite ? null : (uiSuite ?? this.uiSuite),
      lastRunId: clearLastRun ? null : (lastRunId ?? this.lastRunId),
      busy: busy ?? this.busy,
      message: message,
    );
  }
}

class _ExecuteCubit extends Cubit<_ExecuteState> {
  _ExecuteCubit(this._repo) : super(const _ExecuteState());

  final ExecuteRepository _repo;

  Future<void> boot() async {
    try {
      final configs = await _repo.listConfigs();
      final ui = await _repo.uiCatalog();
      final flows = <String>[];
      for (final key in ['flows', 'deterministic', 'release_gate']) {
        final list = ui[key];
        if (list is List) {
          for (final f in list) {
            if (f is Map && f['id'] != null) flows.add('${f['id']}');
            if (f is String) flows.add(f);
          }
        }
      }
      final suites = <String>[];
      final raw = ui['suites'];
      if (raw is List) {
        for (final s in raw) {
          if (s is Map && s['id'] != null) suites.add('${s['id']}');
          if (s is String) suites.add(s);
        }
      }
      if (isClosed) return;
      emit(
        state.copyWith(
          configs: configs,
          flowIds: flows.toSet().toList()..sort(),
          suiteIds: suites.toSet().toList()..sort(),
          configId: configs.isEmpty ? null : '${configs.first['id'] ?? ''}',
        ),
      );
      await _syncFromConfig(state.configId);
    } catch (e) {
      if (!isClosed) emit(state.copyWith(message: e.toString()));
    }
  }

  Future<void> selectConfig(String? id) async {
    emit(state.copyWith(configId: id));
    await _syncFromConfig(id);
  }

  Future<void> _syncFromConfig(String? id) async {
    if (id == null) return;
    final cfg = state.selectedConfig;
    if (cfg == null) return;
    final tt = '${cfg['test_type'] ?? state.testType}';
    final vus = cfg['vus'];
    final iters = cfg['iterations'] ?? cfg['calls'];
    final audience = '${cfg['audience'] ?? 'developer'}';
    final locked = audience != 'developer' && audience.isNotEmpty;
    final selected = <String>{};
    final ids = cfg['selected_api_ids'] ?? cfg['api_ids'];
    if (ids is List) {
      for (final x in ids) {
        selected.add('$x');
      }
    }
    final service = '${cfg['service'] ?? ''}'.trim();
    final env = '${cfg['environment'] ?? 'dev'}'.trim();
    final payloadVer = _payloadVersionFromConfig(cfg);
    emit(
      state.copyWith(
        testType: tt.isEmpty ? state.testType : tt,
        vus: locked ? 1 : (vus is int ? vus : (int.tryParse('$vus') ?? state.vus)),
        calls: locked
            ? 1
            : (iters is int ? iters : (int.tryParse('$iters') ?? state.calls)),
        uiProfile: cfg['ui_profile']?.toString(),
        uiSuite: cfg['ui_suite']?.toString(),
        openapiVersion: cfg['openapi_version']?.toString(),
        payloadSetVersion: payloadVer,
        configEnvironment: env.isEmpty ? null : env,
        configService: service.isEmpty ? null : service,
        selectedApiIds: selected,
        clearUiProfile: cfg['ui_profile'] == null,
        clearUiSuite: cfg['ui_suite'] == null,
        clearPayloadSetVersion: payloadVer == null,
        clearConfigEnvironment: env.isEmpty,
        clearConfigService: service.isEmpty,
      ),
    );
    if (getIt.isRegistered<SpecsProfileDefaults>()) {
      // ignore: unawaited_futures
      getIt<SpecsProfileDefaults>().pushFromConfig(cfg);
    }
    if (service.isNotEmpty) {
      try {
        final apis = await _repo.serviceApis(service, environment: env);
        final versions = await _repo.openapiVersions(service);
        emit(state.copyWith(catalogApis: apis, openapiVersions: versions));
      } catch (_) {}
    }
  }

  static String? _payloadVersionFromConfig(Map<String, dynamic> cfg) {
    return SpecsProfileDefaults.versionFromConfig(cfg);
  }

  void applyPreset(String preset) {
    if (state.audienceLocked) {
      emit(state.copyWith(preset: preset, vus: 1, calls: 1, message: 'Audience locked to 1×1'));
      return;
    }
    switch (preset) {
      case 'smoke':
        emit(state.copyWith(preset: preset, vus: 1, calls: 5, runProfile: 'debug'));
        break;
      case 'load':
        emit(state.copyWith(preset: preset, vus: 10, calls: 50, runProfile: 'load'));
        break;
      case '20u-50':
        emit(state.copyWith(preset: preset, vus: 20, calls: 50, runProfile: 'load'));
        break;
      case 'stress':
        emit(state.copyWith(preset: preset, vus: 50, calls: 200, runProfile: 'load'));
        break;
      default:
        emit(state.copyWith(preset: 'custom'));
    }
  }

  void setTestType(String t) => emit(state.copyWith(testType: t));
  void setVus(int v) {
    if (state.audienceLocked) return;
    emit(state.copyWith(vus: v, preset: 'custom'));
  }

  void setCalls(int c) {
    if (state.audienceLocked) return;
    emit(state.copyWith(calls: c, preset: 'custom'));
  }

  void setRunProfile(String p) {
    if (p == 'debug') {
      emit(state.copyWith(runProfile: p, vus: 1, calls: 1, preset: 'custom'));
    } else {
      emit(state.copyWith(runProfile: p));
    }
  }

  void setReportFormats(List<String> f) => emit(state.copyWith(reportFormats: f));
  void setOpenapiVersion(String? v) =>
      emit(state.copyWith(openapiVersion: v, clearOpenapiVersion: v == null));
  void setUiProfile(String? v) =>
      emit(state.copyWith(uiProfile: v, clearUiProfile: v == null));
  void setUiSuite(String? v) =>
      emit(state.copyWith(uiSuite: v, clearUiSuite: v == null));
  void setSelectedApis(Set<String> ids) => emit(state.copyWith(selectedApiIds: ids));

  Future<String?> run({String? service, String? environment}) async {
    final id = state.configId;
    if (id == null || id.isEmpty) {
      emit(state.copyWith(message: 'Select a profile'));
      return null;
    }
    final cfg = state.selectedConfig;
    final svc = (service ?? '${cfg?['service'] ?? ''}').trim();
    final env = (environment ?? '${cfg?['environment'] ?? ''}').trim();
    emit(state.copyWith(busy: true, message: null));
    try {
      final out = await _repo.execute(
        configId: id,
        // Bind OpenAPI catalog service when template profiles have empty service.
        service: svc.isEmpty ? null : svc,
        environment: env.isEmpty ? null : env,
        testType: state.testType,
        vus: state.vus,
        calls: state.calls,
        profile: state.runProfile,
        uiProfile: state.uiProfile,
        uiSuite: state.uiSuite,
        reportFormats: state.reportFormats,
        // Empty selection = all OpenAPI APIs for the bound service.
        apiIds: state.selectedApiIds.isEmpty ? null : state.selectedApiIds.toList(),
        openapiVersion: state.openapiVersion,
        payloadSet: state.payloadSetVersion,
      );
      final runId = '${out['id'] ?? out['run_id'] ?? ''}';
      emit(state.copyWith(busy: false, message: 'Started', lastRunId: runId));
      return runId;
    } catch (e) {
      emit(state.copyWith(busy: false, message: e.toString()));
      return null;
    }
  }

  Future<void> stopLast() async {
    final id = state.lastRunId;
    if (id == null || id.isEmpty) {
      emit(state.copyWith(message: 'No active run from this bar'));
      return;
    }
    try {
      await _repo.stopRun(id);
      emit(state.copyWith(message: 'Stop requested', clearLastRun: true));
    } catch (e) {
      emit(state.copyWith(message: e.toString()));
    }
  }
}

