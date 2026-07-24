import 'dart:convert';

import 'package:am_design_system/am_design_system.dart';
import 'package:dio/dio.dart';
import 'package:equatable/equatable.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/config/portal_config.dart';
import '../../../../core/di/injection.dart';
import '../../../execute/data/execute_repository.dart';
import '../../data/specs_repository.dart';
import '../../domain/openapi_fill.dart';
import '../../domain/try_draft.dart';
import '../widgets/swagger_embed.dart';
import '../widgets/test_workspace.dart';

class SpecsPage extends StatelessWidget {
  const SpecsPage({super.key});

  @override
  Widget build(BuildContext context) {
    final spec = GoRouterState.of(context).uri.queryParameters['spec'];
    return BlocProvider(
      create: (_) => SpecsCubit(
        getIt<SpecsRepository>(),
        getIt<ExecuteRepository>(),
        getIt<Dio>(),
      )..boot(initialService: spec),
      child: const _SpecsView(),
    );
  }
}

class SpecsState extends Equatable {
  const SpecsState({
    this.loading = false,
    this.services = const [],
    this.serviceLabels = const {},
    this.configs = const [],
    this.selectedService,
    this.environment = 'dev',
    this.apis = const [],
    this.openapi,
    this.openapiDoc,
    this.openapiUrl,
    this.targetUrl,
    this.specRevision = '',
    this.selectedApiId,
    this.selectedApiIds = const {},
    this.payloadSets = const [],
    this.selectedPayloadVersion,
    this.draft = const TryDraft(),
    this.tryResult,
    this.tryStatusCode,
    this.tryDurationMs,
    this.actionResult,
    this.mcpSummary,
    this.tryToken,
    this.canRevert = false,
    this.error,
    this.health,
    this.message,
    this.fileBytes = const {},
    this.lastPayloadDiff = const [],
    this.paramEnums = const {},
  });

  final bool loading;
  final List<String> services;
  final Map<String, String> serviceLabels;
  final List<Map<String, dynamic>> configs;
  final String? selectedService;
  final String environment;
  final List<Map<String, dynamic>> apis;
  final Map<String, dynamic>? openapi;
  /// Stable OpenAPI document reference (do not re-copy on every read).
  final Map<String, dynamic>? openapiDoc;
  final String? openapiUrl;
  /// Catalog service base URL for this env (shareable curl target).
  final String? targetUrl;
  /// Bumps only when Swagger should remount.
  final String specRevision;
  final String? selectedApiId;
  final Set<String> selectedApiIds;
  final List<Map<String, dynamic>> payloadSets;
  final String? selectedPayloadVersion;
  final TryDraft draft;
  final String? tryResult;
  final int? tryStatusCode;
  final int? tryDurationMs;
  final String? actionResult;
  final Map<String, dynamic>? mcpSummary;
  final String? tryToken;
  final bool canRevert;
  final String? error;
  final Map<String, dynamic>? health;
  final String? message;
  final Map<String, ({String name, List<int> bytes})> fileBytes;
  final List<DraftFieldChange> lastPayloadDiff;
  /// OpenAPI enum options for path/query/header param names.
  final Map<String, List<String>> paramEnums;

  String labelFor(String serviceId) => serviceLabels[serviceId] ?? serviceId;

  Map<String, dynamic>? get selectedApi {
    for (var i = 0; i < apis.length; i++) {
      final id = '${apis[i]['id'] ?? apis[i]['operationId'] ?? i}';
      if (id == selectedApiId) return apis[i];
    }
    return null;
  }

  Map<String, dynamic>? get openapiDocument => openapiDoc;

  SpecsState copyWith({
    bool? loading,
    List<String>? services,
    Map<String, String>? serviceLabels,
    List<Map<String, dynamic>>? configs,
    String? selectedService,
    String? environment,
    List<Map<String, dynamic>>? apis,
    Map<String, dynamic>? openapi,
    Map<String, dynamic>? openapiDoc,
    String? openapiUrl,
    String? targetUrl,
    String? specRevision,
    String? selectedApiId,
    Set<String>? selectedApiIds,
    List<Map<String, dynamic>>? payloadSets,
    String? selectedPayloadVersion,
    TryDraft? draft,
    String? tryResult,
    int? tryStatusCode,
    int? tryDurationMs,
    String? actionResult,
    Map<String, dynamic>? mcpSummary,
    String? tryToken,
    bool? canRevert,
    String? error,
    Map<String, dynamic>? health,
    String? message,
    Map<String, ({String name, List<int> bytes})>? fileBytes,
    List<DraftFieldChange>? lastPayloadDiff,
    Map<String, List<String>>? paramEnums,
    bool clearOpenapi = false,
    bool clearOpenapiUrl = false,
    bool clearTargetUrl = false,
    bool clearTryResult = false,
    bool clearActionResult = false,
    bool clearPayloadVersion = false,
    bool clearMcpSummary = false,
    bool clearPayloadDiff = false,
    bool clearParamEnums = false,
  }) {
    return SpecsState(
      loading: loading ?? this.loading,
      services: services ?? this.services,
      serviceLabels: serviceLabels ?? this.serviceLabels,
      configs: configs ?? this.configs,
      selectedService: selectedService ?? this.selectedService,
      environment: environment ?? this.environment,
      apis: apis ?? this.apis,
      openapi: clearOpenapi ? null : (openapi ?? this.openapi),
      openapiDoc: clearOpenapi ? null : (openapiDoc ?? this.openapiDoc),
      openapiUrl: clearOpenapiUrl ? null : (openapiUrl ?? this.openapiUrl),
      targetUrl: clearTargetUrl ? null : (targetUrl ?? this.targetUrl),
      specRevision: specRevision ?? this.specRevision,
      selectedApiId: selectedApiId ?? this.selectedApiId,
      selectedApiIds: selectedApiIds ?? this.selectedApiIds,
      payloadSets: payloadSets ?? this.payloadSets,
      selectedPayloadVersion: clearPayloadVersion
          ? null
          : (selectedPayloadVersion ?? this.selectedPayloadVersion),
      draft: draft ?? this.draft,
      tryResult: clearTryResult ? null : (tryResult ?? this.tryResult),
      tryStatusCode: clearTryResult ? null : (tryStatusCode ?? this.tryStatusCode),
      tryDurationMs: clearTryResult ? null : (tryDurationMs ?? this.tryDurationMs),
      actionResult: clearActionResult ? null : (actionResult ?? this.actionResult),
      mcpSummary: clearMcpSummary ? null : (mcpSummary ?? this.mcpSummary),
      tryToken: tryToken ?? this.tryToken,
      canRevert: canRevert ?? this.canRevert,
      error: error,
      health: health ?? this.health,
      message: message,
      fileBytes: fileBytes ?? this.fileBytes,
      lastPayloadDiff:
          clearPayloadDiff ? const [] : (lastPayloadDiff ?? this.lastPayloadDiff),
      paramEnums: clearParamEnums ? const {} : (paramEnums ?? this.paramEnums),
    );
  }

  @override
  List<Object?> get props => [
        loading,
        services,
        serviceLabels,
        configs,
        selectedService,
        environment,
        apis,
        openapi,
        openapiDoc,
        openapiUrl,
        targetUrl,
        specRevision,
        selectedApiId,
        selectedApiIds,
        payloadSets,
        selectedPayloadVersion,
        draft,
        tryResult,
        tryStatusCode,
        tryDurationMs,
        actionResult,
        mcpSummary,
        tryToken,
        canRevert,
        error,
        health,
        message,
        fileBytes.keys.toList(),
        lastPayloadDiff.length,
        paramEnums.keys.toList(),
      ];
}

class SpecsCubit extends Cubit<SpecsState> {
  SpecsCubit(this._repo, this._executeRepo, this._dio) : super(const SpecsState());

  final SpecsRepository _repo;
  final ExecuteRepository _executeRepo;
  final Dio _dio;
  final TryHistory _history = TryHistory();

  static String apiId(Map<String, dynamic> api, int index) =>
      '${api['id'] ?? api['operationId'] ?? index}';

  static String _prettyJson(Object? value) => prettyJsonValue(value);

  static String _prettyResponseBody(dynamic data) {
    if (data == null) return 'null';
    if (data is String) {
      final t = data.trim();
      if (t.isEmpty) return '';
      try {
        return prettyJsonValue(jsonDecode(t));
      } catch (_) {
        return data;
      }
    }
    return prettyJsonValue(data);
  }

  void _pushHistory() {
    _history.push(state.draft);
    emit(state.copyWith(canRevert: _history.canRevert));
  }

  void updateDraft(TryDraft draft) => emit(state.copyWith(draft: draft));

  void revertDraft() {
    final prev = _history.pop();
    if (prev == null) return;
    emit(state.copyWith(draft: prev, canRevert: _history.canRevert, message: 'Reverted to previous payload'));
  }

  Map<String, dynamic>? _matchConfig(String service, String environment) {
    for (final c in state.configs) {
      final svc = '${c['service'] ?? ''}';
      final env = '${c['environment'] ?? ''}';
      if (svc == service && (env.isEmpty || env == environment)) return c;
    }
    for (final c in state.configs) {
      if ('${c['service'] ?? ''}' == service) return c;
    }
    return null;
  }

  String? _openapiVersion() {
    final info = state.openapiDocument?['info'] ?? state.openapi?['info'];
    if (info is Map && info['version'] != null) return '${info['version']}';
    return null;
  }

  String? _extractOpenapiUrl(Map<String, dynamic> doc) {
    for (final key in ['openapi_url', 'openapi_url_cluster', 'source_url', 'url']) {
      final v = '${doc[key] ?? ''}'.trim();
      if (v.isNotEmpty) return v;
    }
    return null;
  }

  Map<String, dynamic>? _stableDoc(Map<String, dynamic> envelope) {
    final raw = envelope['document'];
    if (raw is Map) return Map<String, dynamic>.from(raw);
    if (envelope.containsKey('paths')) return Map<String, dynamic>.from(envelope);
    return null;
  }

  Future<void> _ensureToken() async {
    if (state.tryToken != null && state.tryToken!.isNotEmpty) return;
    try {
      final t = await _repo.tryToken();
      emit(state.copyWith(tryToken: t, draft: state.draft.copyWith(authBearer: t)));
    } catch (_) {}
  }

  void applyPayloadMap(Map<String, dynamic> payload, {bool pushHistory = true}) {
    if (pushHistory) _pushHistory();
    final request = payload['request'] is Map
        ? Map<String, dynamic>.from(payload['request'] as Map)
        : payload;
    final next = applyRequestOntoDraft(
      state.draft.copyWith(authBearer: state.tryToken ?? state.draft.authBearer),
      request,
      openapiDoc: state.openapiDoc,
    );
    // Pretty request body always when json
    final body = next.bodyMode == 'json' ? prettyJsonValue(next.body) : next.body;
    final enums = extractParamEnums(
      state.openapiDoc,
      method: next.method,
      path: next.path,
    );
    emit(
      state.copyWith(
        draft: next.copyWith(body: body),
        paramEnums: enums,
        canRevert: _history.canRevert,
      ),
    );
  }

  /// Fill Test draft from catalog API row + OpenAPI examples, then overlay payload set.
  Future<void> applyApiToDraft(Map<String, dynamic> api, {bool pushHistory = true}) async {
    if (pushHistory) _pushHistory();
    final method = '${api['method'] ?? 'GET'}'.toUpperCase();
    final path = '${api['path'] ?? api['url'] ?? ''}';
    var draft = TryDraft(
      method: method,
      path: path,
      authBearer: state.tryToken,
      headers: const {'Accept': 'application/json'},
    );
    draft = applyRequestOntoDraft(draft, api, openapiDoc: state.openapiDoc);
    final enums = extractParamEnums(
      state.openapiDoc,
      method: draft.method,
      path: draft.path,
    );
    emit(
      state.copyWith(
        draft: draft.copyWith(
          body: draft.bodyMode == 'json' ? prettyJsonValue(draft.body) : draft.body,
        ),
        paramEnums: enums,
        canRevert: _history.canRevert,
        clearTryResult: true,
        clearActionResult: true,
      ),
    );
    await loadSetApiIntoTry(pushHistory: false);
  }

  Future<void> boot({String? initialService}) async {
    emit(state.copyWith(loading: true, error: null));
    try {
      final health = await _repo.platformHealth();
      final listed = await _repo.listServices();
      final configs = await _executeRepo.listConfigs();
      final list = listed.ids;
      final pick = initialService != null &&
              initialService.isNotEmpty &&
              list.contains(initialService)
          ? initialService
          : (list.isEmpty ? null : list.first);
      emit(
        state.copyWith(
          loading: false,
          services: list,
          serviceLabels: listed.labels,
          configs: configs,
          health: health,
          selectedService: pick,
          message: list.isEmpty ? 'No catalog services.' : null,
        ),
      );
      await _ensureToken();
      if (pick != null) await selectService(pick);
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }

  Future<void> _loadPayloadSets(String service) async {
    try {
      final sets = await _repo.payloadSets(service);
      String? version = state.selectedPayloadVersion;
      if (version == null && sets.isNotEmpty) {
        final active = sets.firstWhere(
          (s) => s['active'] == true || s['is_active'] == true,
          orElse: () => sets.first,
        );
        version = '${active['version'] ?? active['id'] ?? ''}';
        if (version.isEmpty) version = null;
      }
      emit(
        state.copyWith(
          payloadSets: sets,
          selectedPayloadVersion: version,
          clearPayloadVersion: version == null,
        ),
      );
      if (version != null && state.selectedApiId != null) {
        await loadSetApiIntoTry(pushHistory: false);
      }
    } catch (_) {
      emit(state.copyWith(payloadSets: const [], clearPayloadVersion: true));
    }
  }

  Future<void> selectService(String service) async {
    _history.clear();
    emit(
      state.copyWith(
        loading: true,
        selectedService: service,
        selectedApiIds: const {},
        error: null,
        clearActionResult: true,
        clearTryResult: true,
        clearMcpSummary: true,
        clearOpenapiUrl: true,
        canRevert: false,
        fileBytes: const {},
      ),
    );
    try {
      final apis = await _repo.apis(service, environment: state.environment);
      final docEnvelope = await _repo.openapi(service, environment: state.environment);
      final doc = _stableDoc(docEnvelope);
      final target = '${docEnvelope['target_url'] ?? docEnvelope['resolved_target'] ?? ''}'.trim();
      final first = apis.isEmpty ? null : apis.first;
      final firstId = first == null ? null : apiId(first, 0);
      final rev =
          '$service|${state.environment}|${docEnvelope['version'] ?? ''}|${docEnvelope['path_count'] ?? doc?['paths']?.length ?? 0}';
      emit(
        state.copyWith(
          loading: false,
          apis: apis,
          openapi: docEnvelope,
          openapiDoc: doc,
          openapiUrl: _extractOpenapiUrl(docEnvelope),
          targetUrl: target.isEmpty ? null : target,
          clearTargetUrl: target.isEmpty,
          specRevision: rev,
          selectedApiId: firstId,
          draft: TryDraft(authBearer: state.tryToken),
          clearPayloadDiff: true,
          clearParamEnums: true,
        ),
      );
      if (first != null) {
        await applyApiToDraft(first, pushHistory: false);
      }
      await _loadPayloadSets(service);
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }

  void setEnvironment(String env) {
    emit(state.copyWith(environment: env));
    final svc = state.selectedService;
    if (svc != null) selectService(svc);
  }

  Future<void> pickApi(Map<String, dynamic> api) async {
    final index = state.apis.indexOf(api);
    emit(
      state.copyWith(
        selectedApiId: apiId(api, index < 0 ? 0 : index),
        clearTryResult: true,
        clearActionResult: true,
      ),
    );
    await applyApiToDraft(api);
  }

  void toggleApiSelection(String id, {required bool selected}) {
    final next = Set<String>.from(state.selectedApiIds);
    if (selected) {
      next.add(id);
    } else {
      next.remove(id);
    }
    emit(state.copyWith(selectedApiIds: next));
  }

  void selectAllApis() {
    final all = <String>{};
    for (var i = 0; i < state.apis.length; i++) {
      all.add(apiId(state.apis[i], i));
    }
    emit(state.copyWith(selectedApiIds: all));
  }

  void clearApiSelection() => emit(state.copyWith(selectedApiIds: const {}));

  Future<void> setPayloadVersion(String? version) async {
    emit(
      state.copyWith(
        selectedPayloadVersion: version,
        clearPayloadVersion: version == null,
      ),
    );
    if (version != null) await loadSetApiIntoTry();
  }

  Future<void> loadSetApiIntoTry({bool pushHistory = true}) async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    final id = state.selectedApiId;
    if (svc == null || ver == null || id == null) return;
    try {
      final set = await _repo.getPayloadSet(svc, ver);
      final apis = set['apis'];
      if (apis is! Map) return;
      dynamic entry = apis[id] ?? apis[id.replaceAll('.', '_')];
      if (entry == null) {
        final lower = id.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
        for (final e in apis.entries) {
          final k = '${e.key}'.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
          if (k == lower) {
            entry = e.value;
            break;
          }
        }
      }
      if (entry is Map) {
        applyPayloadMap(Map<String, dynamic>.from(entry), pushHistory: pushHistory);
      }
    } catch (_) {}
  }

  Future<void> formatBody() async {
    try {
      final formatted = formatJsonBody(state.draft.body);
      if (formatted == null) return;
      emit(state.copyWith(
        draft: state.draft.copyWith(body: formatted, bodyMode: 'json'),
        message: 'JSON formatted',
      ));
    } catch (e) {
      emit(state.copyWith(message: 'Invalid JSON: $e'));
    }
  }

  Future<void> refreshPayload() async {
    final before = state.draft.snapshot();
    _pushHistory();
    try {
      await ensureWorking(apply: true, pushHistory: false);
      final after = state.draft.snapshot();
      final diff = describeDraftDiff(before, after);
      emit(
        state.copyWith(
          lastPayloadDiff: diff,
          message: diff.isEmpty
              ? 'Refresh: no changes vs previous draft'
              : 'Refresh: ${diff.length} field(s) changed ? compare shown',
        ),
      );
    } catch (e) {
      final prev = _history.pop();
      if (prev != null) {
        emit(state.copyWith(
          draft: prev,
          canRevert: _history.canRevert,
          clearPayloadDiff: true,
          message: 'Refresh failed ? restored previous payload',
        ));
      } else {
        emit(state.copyWith(message: 'Refresh failed: $e', clearPayloadDiff: true));
      }
    }
  }

  void clearPayloadDiff() => emit(state.copyWith(clearPayloadDiff: true));

  Future<String?> runLoad({bool mockOne = false}) async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service'));
      return null;
    }
    final ids = state.selectedApiIds.isNotEmpty
        ? state.selectedApiIds.toList()
        : (state.selectedApiId != null ? [state.selectedApiId!] : <String>[]);
    if (ids.isEmpty) {
      emit(state.copyWith(message: 'Select at least one API'));
      return null;
    }
    final cfg = _matchConfig(svc, state.environment);
    if (cfg == null) {
      emit(state.copyWith(message: 'No load config for $svc'));
      return null;
    }
    final configId = '${cfg['id'] ?? ''}';
    if (configId.isEmpty) {
      emit(state.copyWith(message: 'No load config for $svc'));
      return null;
    }
    emit(state.copyWith(loading: true, message: null));
    try {
      final out = await _executeRepo.execute(
        configId: configId,
        profile: mockOne ? 'debug' : 'load',
        vus: mockOne ? 1 : 20,
        calls: mockOne ? 1 : 50,
        apiIds: ids,
        openapiVersion: _openapiVersion(),
        payloadSet: state.selectedPayloadVersion,
      );
      final runId = '${out['id'] ?? out['run_id'] ?? ''}';
      emit(state.copyWith(loading: false, message: mockOne ? 'Mock 1? started' : 'Load started'));
      return runId.isEmpty ? null : runId;
    } catch (e) {
      emit(state.copyWith(loading: false, message: e.toString()));
      return null;
    }
  }

  Future<void> ensurePayloadSet() async {
    final svc = state.selectedService;
    if (svc == null) return;
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await _repo.ensurePayloadSet(svc);
      await _loadPayloadSets(svc);
      emit(state.copyWith(loading: false, actionResult: _prettyJson(out), message: 'Payload set ensured'));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString()));
    }
  }

  Future<void> activatePayloadVersion(String version) async {
    final svc = state.selectedService;
    if (svc == null || version.isEmpty) return;
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await _repo.activatePayloadSet(svc, version);
      await _loadPayloadSets(svc);
      emit(state.copyWith(
        loading: false,
        selectedPayloadVersion: version,
        actionResult: _prettyJson(out),
        message: 'Activated v$version',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString()));
    }
  }

  Future<void> saveToCurrentSet({bool bumpSet = false}) async {
    final svc = state.selectedService;
    final apiId = state.selectedApiId;
    if (svc == null || apiId == null) {
      emit(state.copyWith(message: 'Select a service and API'));
      return;
    }
    final ver = state.selectedPayloadVersion;
    Object? body;
    if (state.draft.body.trim().isNotEmpty && state.draft.bodyMode != 'none') {
      try {
        body = jsonDecode(state.draft.body);
      } catch (_) {
        body = state.draft.body;
      }
    }
    final request = <String, dynamic>{
      'method': state.draft.method,
      'path': state.draft.path,
      if (state.draft.pathParams.isNotEmpty) 'path_params': state.draft.pathParams,
      if (state.draft.queryParams.isNotEmpty) 'query': state.draft.queryParams,
      if (state.draft.headers.isNotEmpty) 'headers': state.draft.headers,
      if (body != null) 'body': body,
    };
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await _repo.savePayload(
        service: svc,
        apiId: apiId,
        request: request,
        name: 'working',
        setVersion: ver == null ? null : int.tryParse(ver),
        intoSet: true,
        bumpSet: bumpSet,
      );
      await _loadPayloadSets(svc);
      emit(state.copyWith(
        loading: false,
        actionResult: _prettyJson(out),
        message: bumpSet ? 'Saved + bumped set' : 'Saved to v${ver ?? 'active'}',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString(), message: '$e'));
    }
  }

  Future<void> buildPayload({bool apply = true}) async {
    if (state.selectedService == null || state.draft.path.isEmpty) {
      emit(state.copyWith(actionResult: 'Select an API first'));
      return;
    }
    emit(state.copyWith(loading: true, clearActionResult: true));
    try {
      final out = await _repo.buildPayload(
        service: state.selectedService!,
        environment: state.environment,
        method: state.draft.method,
        path: state.draft.path,
      );
      if (apply) applyPayloadMap(out);
      emit(state.copyWith(loading: false, actionResult: _prettyJson(out)));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString()));
    }
  }

  Future<void> ensureWorking({bool apply = true, bool pushHistory = true}) async {
    if (state.selectedService == null || state.draft.path.isEmpty) {
      emit(state.copyWith(actionResult: 'Select an API first'));
      return;
    }
    emit(state.copyWith(loading: true, clearActionResult: true));
    try {
      final out = await _repo.ensureWorking(
        service: state.selectedService!,
        environment: state.environment,
        method: state.draft.method,
        path: state.draft.path,
      );
      await _loadPayloadSets(state.selectedService!);
      if (apply) applyPayloadMap(out, pushHistory: pushHistory);
      emit(state.copyWith(
        loading: false,
        actionResult: _prettyJson(out),
        message: out['ok'] == true ? 'Working payload ready' : 'Ensure finished',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString()));
      rethrow;
    }
  }

  Future<void> prepareMcp() async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(actionResult: 'Select a service first'));
      return;
    }
    emit(state.copyWith(loading: true, clearActionResult: true, clearMcpSummary: true));
    try {
      final out = await _repo.prepareMcp(service: svc, environment: state.environment);
      await _loadPayloadSets(svc);
      emit(state.copyWith(
        loading: false,
        actionResult: _prettyJson(out),
        mcpSummary: {
          'mapped_count': out['mapped_count'],
          'mapped': out['mapped'],
          'skipped': out['skipped'],
          'portfolio_id': out['portfolio_id'],
        },
        message: 'MCP prepare done (${out['mapped_count'] ?? 0} mapped)',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString()));
    }
  }

  Future<void> aiMakeWork() async {
    _pushHistory();
    try {
      await ensureWorking(apply: true, pushHistory: false);
      await runTry();
    } catch (_) {
      revertDraft();
    }
  }

  Future<void> pickFile(String field) async {
    final result = await FilePicker.platform.pickFiles(withData: true);
    if (result == null || result.files.isEmpty) return;
    final f = result.files.first;
    final bytes = f.bytes;
    if (bytes == null) {
      emit(state.copyWith(message: 'Could not read file bytes'));
      return;
    }
    final files = Map<String, ({String name, List<int> bytes})>.from(state.fileBytes);
    files[field] = (name: f.name, bytes: bytes);
    final fields = Map<String, String>.from(state.draft.fileFields)..[field] = f.name;
    emit(state.copyWith(
      fileBytes: files,
      draft: state.draft.copyWith(fileFields: fields, bodyMode: 'multipart'),
    ));
  }

  void removeFile(String field) {
    final files = Map<String, ({String name, List<int> bytes})>.from(state.fileBytes)..remove(field);
    final fields = Map<String, String>.from(state.draft.fileFields)..remove(field);
    emit(state.copyWith(fileBytes: files, draft: state.draft.copyWith(fileFields: fields)));
  }

  String copyCurlText() {
    final target = (state.targetUrl ?? '').trim();
    var pathOnly = state.draft.resolvedPath.trim();
    if (pathOnly.isEmpty) pathOnly = '/';
    if (!pathOnly.startsWith('/')) pathOnly = '/$pathOnly';
    final q = state.draft.queryParams.entries
        .where((e) => e.value.isNotEmpty)
        .map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}')
        .join('&');
    // Catalog service target for this env ? shareable against real API, not SPT try proxy.
    final baseUrl = target.isNotEmpty
        ? joinBasePath(target, pathOnly)
        : 'https://{${state.selectedService ?? 'service'}-${state.environment}}$pathOnly';
    final url = q.isEmpty ? baseUrl : '$baseUrl?$q';
    final headers = Map<String, String>.from(state.draft.headers)
      ..putIfAbsent('Accept', () => 'application/json');
    return buildCurl(
      method: state.draft.method,
      url: url,
      headers: headers,
      bearer: state.tryToken ?? state.draft.authBearer,
      body: state.draft.body,
      bodyMode: state.draft.bodyMode,
    );
  }

  Future<void> runTry() async {
    final svc = state.selectedService;
    final pathTemplate = state.draft.resolvedPath;
    if (svc == null || pathTemplate.isEmpty) {
      emit(state.copyWith(tryResult: 'Select service and path'));
      return;
    }
    if (pathParamRe.hasMatch(pathTemplate)) {
      emit(state.copyWith(tryResult: 'Fill path params: $pathTemplate', message: 'Unresolved path params'));
      return;
    }
    await _ensureToken();
    emit(state.copyWith(loading: true, tryResult: null, error: null));
    final sw = Stopwatch()..start();
    try {
      Object? body;
      dynamic data;
      final headers = <String, dynamic>{
        ...state.draft.headers,
        if (state.tryToken != null && state.tryToken!.isNotEmpty)
          'Authorization': 'Bearer ${state.tryToken}',
      };

      if (state.draft.bodyMode == 'multipart' && state.fileBytes.isNotEmpty) {
        final form = FormData();
        state.fileBytes.forEach((field, file) {
          form.files.add(MapEntry(
            field,
            MultipartFile.fromBytes(file.bytes, filename: file.name),
          ));
        });
        if (state.draft.body.trim().isNotEmpty) {
          form.fields.add(MapEntry('payload', state.draft.body));
        }
        data = form;
      } else if (state.draft.bodyMode != 'none' && state.draft.body.trim().isNotEmpty) {
        if (state.draft.bodyMode == 'json') {
          body = jsonDecode(state.draft.body);
          headers.putIfAbsent('Content-Type', () => 'application/json');
        } else {
          body = state.draft.body;
        }
        data = body;
      }

      var path = pathTemplate.startsWith('/') ? pathTemplate.substring(1) : pathTemplate;
      if (state.draft.queryParams.isNotEmpty) {
        final q = state.draft.queryParams.entries
            .where((e) => e.value.isNotEmpty)
            .map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}')
            .join('&');
        if (q.isNotEmpty) path = '$path?$q';
      }
      final url = '/api/catalog/$svc/try/${state.environment}/$path';
      final res = await _dio.request<dynamic>(
        url,
        data: data,
        options: Options(
          method: state.draft.method,
          headers: headers,
          validateStatus: (_) => true,
        ),
      );
      sw.stop();
      final prettyData = _prettyResponseBody(res.data);
      emit(state.copyWith(
        loading: false,
        tryStatusCode: res.statusCode,
        tryDurationMs: sw.elapsedMilliseconds,
        tryResult: prettyData,
      ));
    } catch (e) {
      sw.stop();
      emit(state.copyWith(
        loading: false,
        tryDurationMs: sw.elapsedMilliseconds,
        tryResult: e.toString(),
      ));
    }
  }
}



class _SpecsView extends StatefulWidget {
  const _SpecsView();

  @override
  State<_SpecsView> createState() => _SpecsViewState();
}

class _SpecsViewState extends State<_SpecsView> with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  String _serviceQuery = '';
  String _apiQuery = '';

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  List<String> _filteredServices(SpecsState state) {
    final q = _serviceQuery.trim().toLowerCase();
    if (q.isEmpty) return state.services;
    return state.services.where((id) {
      final label = state.labelFor(id).toLowerCase();
      return id.toLowerCase().contains(q) || label.contains(q);
    }).toList();
  }

  List<(int, Map<String, dynamic>)> _filteredApis(SpecsState state) {
    final q = _apiQuery.trim().toLowerCase();
    final out = <(int, Map<String, dynamic>)>[];
    for (var i = 0; i < state.apis.length; i++) {
      final api = state.apis[i];
      final id = SpecsCubit.apiId(api, i).toLowerCase();
      final method = '${api['method'] ?? ''}'.toLowerCase();
      final path = '${api['path'] ?? api['url'] ?? ''}'.toLowerCase();
      if (q.isEmpty || id.contains(q) || method.contains(q) || path.contains(q)) {
        out.add((i, api));
      }
    }
    return out;
  }

  String _tryBase() {
    final cfg = getIt<PortalConfig>();
    return cfg.apiBase.replaceAll(RegExp(r'/$'), '');
  }

  Future<void> _showDiffDialog(BuildContext context, List<DraftFieldChange> diff) async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(diff.isEmpty ? 'Refresh payload ? no changes' : 'Refresh payload ? compare'),
        content: SizedBox(
          width: 720,
          child: diff.isEmpty
              ? const Text('Draft is unchanged after Ensure/refresh.')
              : SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      for (final c in diff) ...[
                        Text(
                          c.field,
                          style: Theme.of(ctx).textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                        const SizedBox(height: 4),
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Theme.of(ctx)
                                      .colorScheme
                                      .errorContainer
                                      .withValues(alpha: 0.35),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: SelectableText(
                                  'Before\n${c.before}',
                                  style: Theme.of(ctx).textTheme.bodySmall?.copyWith(
                                        fontFamily: 'monospace',
                                      ),
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Theme.of(ctx)
                                      .colorScheme
                                      .primaryContainer
                                      .withValues(alpha: 0.35),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: SelectableText(
                                  'After\n${c.after}',
                                  style: Theme.of(ctx).textTheme.bodySmall?.copyWith(
                                        fontFamily: 'monospace',
                                      ),
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                      ],
                    ],
                  ),
                ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              context.read<SpecsCubit>().clearPayloadDiff();
              Navigator.pop(ctx);
            },
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocListener(
      listeners: [
        BlocListener<SpecsCubit, SpecsState>(
          listenWhen: (p, n) => p.message != n.message && n.message != null,
          listener: (context, state) {
            final msg = state.message;
            if (msg == null) return;
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
          },
        ),
        BlocListener<SpecsCubit, SpecsState>(
          listenWhen: (p, n) =>
              p.message != n.message && n.message != null && n.message!.startsWith('Refresh:'),
          listener: (context, state) {
            _showDiffDialog(context, state.lastPayloadDiff);
          },
        ),
      ],
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Theme.of(context).colorScheme.surface,
              AppColors.primary.withValues(alpha: 0.06),
              Theme.of(context).colorScheme.surface,
            ],
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(8, 6, 8, 8),
          child: BlocBuilder<SpecsCubit, SpecsState>(
            builder: (context, state) {
              if (state.loading && state.services.isEmpty) {
                return const Center(child: CircularProgressIndicator());
              }
              final cubit = context.read<SpecsCubit>();
              final services = _filteredServices(state);
              final apis = _filteredApis(state);
              final versions = <String>{
                for (final s in state.payloadSets) '${s['version'] ?? s['id'] ?? ''}',
              }..remove('');
              final selectedVer = state.selectedPayloadVersion;
              final doc = state.openapiDoc ?? const <String, dynamic>{};

              return Column(
                children: [
                  Row(
                    children: [
                      Text(
                        state.selectedService == null
                            ? 'OpenAPI'
                            : state.labelFor(state.selectedService!),
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                      const SizedBox(width: 8),
                      if (state.targetUrl != null)
                        Flexible(
                          child: Text(
                            '${state.environment} · ${state.targetUrl}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  fontFamily: 'monospace',
                                  color: AppColors.textSecondaryDark,
                                ),
                          ),
                        ),
                      const Spacer(),
                      if (state.loading)
                        const Padding(
                          padding: EdgeInsets.only(left: 8),
                          child: SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Expanded(
                    child: Row(
                      children: [
                        SizedBox(
                          width: 200,
                          child: GlassCard(
                            padding: EdgeInsets.zero,
                            child: Column(
                              children: [
                                Padding(
                                  padding: const EdgeInsets.fromLTRB(8, 8, 8, 4),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.stretch,
                                    children: [
                                      Row(
                                        children: [
                                          Expanded(
                                            child: Text(
                                              'Catalog (${services.length})',
                                              style: Theme.of(context).textTheme.labelLarge,
                                            ),
                                          ),
                                          SizedBox(
                                            width: 88,
                                            child: DropdownButtonFormField<String>(
                                              key: ValueKey(state.environment),
                                              initialValue: state.environment,
                                              isDense: true,
                                              decoration: const InputDecoration(
                                                isDense: true,
                                                border: OutlineInputBorder(),
                                                contentPadding: EdgeInsets.symmetric(
                                                  horizontal: 8,
                                                  vertical: 6,
                                                ),
                                              ),
                                              items: const [
                                                DropdownMenuItem(value: 'dev', child: Text('dev')),
                                                DropdownMenuItem(
                                                  value: 'preprod',
                                                  child: Text('preprod'),
                                                ),
                                                DropdownMenuItem(value: 'prod', child: Text('prod')),
                                              ],
                                              onChanged: (v) {
                                                if (v != null) cubit.setEnvironment(v);
                                              },
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 6),
                                      TextField(
                                        decoration: const InputDecoration(
                                          hintText: 'Filter services',
                                          isDense: true,
                                          border: OutlineInputBorder(),
                                          prefixIcon: Icon(Icons.search, size: 16),
                                        ),
                                        onChanged: (v) => setState(() => _serviceQuery = v),
                                      ),
                                      Text(
                                        'health: ${state.health?['status'] ?? '?'}',
                                        style: Theme.of(context).textTheme.bodySmall,
                                      ),
                                    ],
                                  ),
                                ),
                                const Divider(height: 1),
                                Expanded(
                                  child: ListView.builder(
                                    itemCount: services.length,
                                    itemBuilder: (_, i) {
                                      final id = services[i];
                                      return ListTile(
                                        dense: true,
                                        selected: id == state.selectedService,
                                        selectedTileColor:
                                            AppColors.primary.withValues(alpha: 0.14),
                                        title: Text(state.labelFor(id), maxLines: 1),
                                        onTap: () => cubit.selectService(id),
                                      );
                                    },
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        SizedBox(
                          width: 270,
                          child: GlassCard(
                            padding: EdgeInsets.zero,
                            child: Column(
                              children: [
                                Padding(
                                  padding: const EdgeInsets.fromLTRB(8, 8, 8, 4),
                                  child: Column(
                                    children: [
                                      Row(
                                        children: [
                                          Expanded(
                                            child: Text(
                                              'APIs (${apis.length})',
                                              style: Theme.of(context).textTheme.labelLarge,
                                            ),
                                          ),
                                          TextButton(
                                            onPressed: cubit.selectAllApis,
                                            child: const Text('All'),
                                          ),
                                          TextButton(
                                            onPressed: cubit.clearApiSelection,
                                            child: const Text('Clear'),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Row(
                                        children: [
                                          Expanded(
                                            child: TextField(
                                              decoration: const InputDecoration(
                                                hintText: 'Filter APIs',
                                                isDense: true,
                                                border: OutlineInputBorder(),
                                                prefixIcon: Icon(Icons.filter_list, size: 16),
                                              ),
                                              onChanged: (v) => setState(() => _apiQuery = v),
                                            ),
                                          ),
                                          const SizedBox(width: 6),
                                          SizedBox(
                                            width: 92,
                                            child: DropdownButtonFormField<String?>(
                                              key: ValueKey('ver-$selectedVer'),
                                              initialValue: selectedVer != null &&
                                                      versions.contains(selectedVer)
                                                  ? selectedVer
                                                  : null,
                                              isDense: true,
                                              decoration: const InputDecoration(
                                                labelText: 'v',
                                                isDense: true,
                                                border: OutlineInputBorder(),
                                                contentPadding: EdgeInsets.symmetric(
                                                  horizontal: 6,
                                                  vertical: 4,
                                                ),
                                              ),
                                              items: [
                                                const DropdownMenuItem(
                                                  value: null,
                                                  child: Text('(none)'),
                                                ),
                                                for (final v in versions.toList()..sort())
                                                  DropdownMenuItem(value: v, child: Text('v$v')),
                                              ],
                                              onChanged:
                                                  state.loading ? null : cubit.setPayloadVersion,
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Row(
                                        children: [
                                          Text(
                                            '${state.selectedApiIds.length}/${state.apis.length}',
                                            style: Theme.of(context).textTheme.bodySmall,
                                          ),
                                          const Spacer(),
                                          TextButton(
                                            onPressed: state.loading ||
                                                    state.selectedService == null
                                                ? null
                                                : cubit.ensurePayloadSet,
                                            child: const Text('Ensure'),
                                          ),
                                          TextButton(
                                            onPressed: state.loading || selectedVer == null
                                                ? null
                                                : () => cubit.activatePayloadVersion(selectedVer),
                                            child: const Text('Activate'),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                                const Divider(height: 1),
                                Expanded(
                                  child: ListView.separated(
                                    itemCount: apis.length,
                                    separatorBuilder: (_, __) => const Divider(height: 1),
                                    itemBuilder: (_, i) {
                                      final (index, api) = apis[i];
                                      final id = SpecsCubit.apiId(api, index);
                                      final method = '${api['method'] ?? ''}'.toUpperCase();
                                      final path = '${api['path'] ?? api['url'] ?? ''}';
                                      final checked = state.selectedApiIds.contains(id);
                                      return ListTile(
                                        dense: true,
                                        selected: id == state.selectedApiId,
                                        selectedTileColor:
                                            AppColors.primary.withValues(alpha: 0.1),
                                        leading: Checkbox(
                                          value: checked,
                                          onChanged: (v) => cubit.toggleApiSelection(
                                            id,
                                            selected: v == true,
                                          ),
                                        ),
                                        title: Row(
                                          children: [
                                            Container(
                                              padding: const EdgeInsets.symmetric(
                                                horizontal: 5,
                                                vertical: 1,
                                              ),
                                              decoration: BoxDecoration(
                                                color: _methodBg(method),
                                                borderRadius: BorderRadius.circular(4),
                                              ),
                                              child: Text(
                                                method,
                                                style: TextStyle(
                                                  fontSize: 10,
                                                  fontWeight: FontWeight.w700,
                                                  color: _methodFg(method),
                                                ),
                                              ),
                                            ),
                                            const SizedBox(width: 6),
                                            Expanded(
                                              child: Text(
                                                path,
                                                maxLines: 1,
                                                overflow: TextOverflow.ellipsis,
                                                style: const TextStyle(fontSize: 12),
                                              ),
                                            ),
                                          ],
                                        ),
                                        onTap: () => cubit.pickApi(api),
                                      );
                                    },
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: GlassCard(
                            padding: EdgeInsets.zero,
                            child: Column(
                              children: [
                                TabBar(
                                  controller: _tabs,
                                  tabs: const [
                                    Tab(text: 'Test'),
                                    Tab(text: 'Swagger'),
                                    Tab(text: 'MCP / AI'),
                                  ],
                                ),
                                Expanded(
                                  child: TabBarView(
                                    controller: _tabs,
                                    children: [
                                      TestWorkspace(
                                        draft: state.draft,
                                        loading: state.loading,
                                        tryResult: state.tryResult,
                                        tryStatusCode: state.tryStatusCode,
                                        tryDurationMs: state.tryDurationMs,
                                        canRevert: state.canRevert,
                                        selectedPayloadVersion: selectedVer,
                                        targetUrl: state.targetUrl,
                                        paramEnums: state.paramEnums,
                                        onDraftChanged: cubit.updateDraft,
                                        onSend: cubit.runTry,
                                        onMock: cubit.runTry,
                                        onFormat: cubit.formatBody,
                                        onBuild: () => cubit.buildPayload(),
                                        onEnsure: () => cubit.ensureWorking(),
                                        onRefreshPayload: cubit.refreshPayload,
                                        onRevert: cubit.revertDraft,
                                        onCopyCurl: () {
                                          Clipboard.setData(
                                            ClipboardData(text: cubit.copyCurlText()),
                                          );
                                          final tgt = state.targetUrl ?? 'catalog target';
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            SnackBar(content: Text('curl copied ? $tgt')),
                                          );
                                        },
                                        onCopyResponse: () {
                                          if (state.tryResult == null) return;
                                          Clipboard.setData(
                                            ClipboardData(text: state.tryResult!),
                                          );
                                        },
                                        onSaveSet: () => cubit.saveToCurrentSet(),
                                        onPickFile: cubit.pickFile,
                                        onRemoveFile: cubit.removeFile,
                                      ),
                                      state.selectedService == null
                                          ? const Center(child: Text('Select a catalog service'))
                                          : SwaggerEmbed(
                                              spec: doc,
                                              specRevision: state.specRevision,
                                              service: state.selectedService!,
                                              environment: state.environment,
                                              tryBase: _tryBase(),
                                              token: state.tryToken,
                                              onRefresh: () => cubit.selectService(
                                                state.selectedService!,
                                              ),
                                              onUseInTest: (draft) {
                                                cubit.applyPayloadMap(draft);
                                                _tabs.index = 0;
                                                ScaffoldMessenger.of(context).showSnackBar(
                                                  const SnackBar(content: Text('Applied to Test')),
                                                );
                                                setState(() {});
                                              },
                                            ),
                                      _McpPane(state: state),
                                    ],
                                  ),
                                ),
                              ],
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
        ),
      ),
    );
  }

  Color _methodBg(String m) {
    switch (m) {
      case 'GET':
        return const Color(0xFF22C55E).withValues(alpha: 0.2);
      case 'POST':
        return AppColors.primary.withValues(alpha: 0.2);
      case 'DELETE':
        return const Color(0xFFEF4444).withValues(alpha: 0.2);
      default:
        return AppColors.primary.withValues(alpha: 0.12);
    }
  }

  Color _methodFg(String m) {
    switch (m) {
      case 'GET':
        return const Color(0xFF22C55E);
      case 'DELETE':
        return const Color(0xFFEF4444);
      default:
        return AppColors.primary;
    }
  }
}

class _McpPane extends StatelessWidget {
  const _McpPane({required this.state});

  final SpecsState state;

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<SpecsCubit>();
    final summary = state.mcpSummary;
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('MCP + AI assist', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton(
                onPressed:
                    state.loading || state.selectedService == null ? null : cubit.prepareMcp,
                child: const Text('Prepare MCP'),
              ),
              FilledButton.tonal(
                onPressed: state.loading ? null : () => cubit.ensureWorking(),
                child: const Text('Ensure + apply'),
              ),
              OutlinedButton(
                onPressed: state.loading ? null : cubit.aiMakeWork,
                child: const Text('AI: make call work'),
              ),
            ],
          ),
          if (summary != null) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              children: [
                Chip(label: Text('mapped: ${summary['mapped_count'] ?? 0}')),
                if (summary['portfolio_id'] != null)
                  Chip(label: Text('portfolio: ${summary['portfolio_id']}')),
              ],
            ),
          ],
          const SizedBox(height: 10),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Theme.of(context)
                    .colorScheme
                    .surfaceContainerHighest
                    .withValues(alpha: 0.35),
                borderRadius: BorderRadius.circular(8),
              ),
              child: SingleChildScrollView(
                child: SelectableText(
                  state.actionResult ?? 'MCP / Ensure output appears here.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontFamily: 'monospace',
                      ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
