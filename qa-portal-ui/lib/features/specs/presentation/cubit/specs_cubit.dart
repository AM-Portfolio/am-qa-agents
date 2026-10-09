import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/config/portal_config.dart';
import '../../../../core/di/injection.dart';
import '../../../../core/network/json_lists.dart';
import '../../../execute/data/execute_repository.dart';
import '../../data/specs_repository.dart';
import '../../domain/openapi_fill.dart';
import '../../domain/try_draft.dart';
import 'specs_cubit_catalog.mixin.dart';
import 'specs_cubit_data.mixin.dart';
import 'specs_cubit_mcp.mixin.dart';
import 'specs_cubit_test.mixin.dart';
import 'specs_cubit_usecases.mixin.dart';
import 'specs_state.dart';

export 'specs_state.dart';

class SpecsCubit extends Cubit<SpecsState>
    with
        SpecsCubitCatalogMixin,
        SpecsCubitTestMixin,
        SpecsCubitDataMixin,
        SpecsCubitUseCasesMixin,
        SpecsCubitMcpMixin {
  SpecsCubit(this.repo, this.executeRepo, this.dio) : super(const SpecsState());

  @override
  final SpecsRepository repo;
  final ExecuteRepository executeRepo;
  final Dio dio;
  final TryHistory history = TryHistory();
  /// Last picked Postman collection awaiting env merge / re-import.
  Map<String, dynamic>? pendingImportCollection;
  /// Bumped on every [selectService] so stale ensure* responses are ignored.
  int _loadGen = 0;
  /// Service id for which /apis has completed (even if empty).
  String? _apisFetchedFor;

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
    history.push(state.draft);
    emit(state.copyWith(canRevert: history.canRevert));
  }

  void updateDraft(TryDraft draft) => emit(state.copyWith(draft: draft));

  void revertDraft() {
    final prev = history.pop();
    if (prev == null) return;
    emit(state.copyWith(draft: prev, canRevert: history.canRevert, message: 'Reverted to previous payload'));
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

  Future<void> _ensureToken({bool force = false}) async {
    if (!force && state.tryToken != null && state.tryToken!.isNotEmpty) return;
    try {
      final t = await repo.tryToken(environment: state.environment);
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
        canRevert: history.canRevert,
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
        canRevert: history.canRevert,
        clearTryResult: true,
        clearActionResult: true,
      ),
    );
    await loadSetApiIntoTry(pushHistory: false);
  }

  bool _serviceHasRealApis(List<Map<String, dynamic>> apis) {
    final real = apis.where((a) {
      final aid = '${a['id'] ?? ''}';
      return aid != 'health-fallback' && !aid.endsWith('.health-fallback');
    }).toList();
    if (real.isNotEmpty || apis.length > 1) return true;
    if (apis.isEmpty) return false;
    final only = '${apis.first['id'] ?? ''}';
    return only != 'health-fallback';
  }

  List<String> _orderServices(Iterable<String> ids) {
    final kept = ids.toList()..sort();
    if (kept.contains('am-subscription')) {
      kept.remove('am-subscription');
      kept.insert(0, 'am-subscription');
    }
    return kept;
  }

  /// Show catalog immediately, then prune services that return a confirmed empty
  /// OpenAPI list. Timeouts/errors keep the service (slow sync must not hide it).
  Future<void> _pruneEmptyServicesInBackground({
    required List<String> ids,
    required Map<String, String> labels,
    required String env,
  }) async {
    if (ids.isEmpty) return;
    // Parallel /apis on remotedev starves Specs (sync OpenAPI on the event loop)
    // and Dio hits connectTimeout 45s with APIs (0). Skip prune when not local.
    final base = dio.options.baseUrl.toLowerCase();
    final remotedev = base.startsWith('https://') ||
        base == '/qa' ||
        base.startsWith('/qa/') ||
        (base.isNotEmpty && !base.contains('localhost') && !base.contains('127.0.0.1'));
    if (remotedev) return;

    // Local Specs: still cap concurrency so selectService keeps a free slot.
    const maxConcurrent = 2;
    await Future<void>.delayed(const Duration(seconds: 2));
    if (isClosed) return;
    final empty = <String>{};
    for (var i = 0; i < ids.length; i += maxConcurrent) {
      final batch = ids.skip(i).take(maxConcurrent).toList(growable: false);
      await Future.wait(
        batch.map((id) async {
          try {
            final apis = await repo
                .apis(id, environment: env)
                .timeout(const Duration(seconds: 25));
            if (!_serviceHasRealApis(apis)) empty.add(id);
          } catch (_) {
            // Keep on timeout/error — e.g. am-subscription OpenAPI sync is slow.
          }
        }),
      );
      if (isClosed) return;
    }
    if (empty.isEmpty) return;
    final selected = state.selectedService;
    final kept = _orderServices(
      state.services.where((id) {
        if (id == selected) return true;
        // Never drop the preferred billing service on a transient empty probe.
        if (id == 'am-subscription') return true;
        return !empty.contains(id);
      }),
    );
    if (kept.length == state.services.length) return;
    emit(
      state.copyWith(
        services: kept,
        serviceLabels: {
          for (final id in kept) id: labels[id] ?? state.labelFor(id),
        },
      ),
    );
  }

  Future<void> boot({
    String? initialService,
    SpecsNavMode? initialNavMode,
    SpecsWorkspaceTab? initialTab,
    String? initialPayloadVersion,
  }) async {
    emit(state.copyWith(loading: true, error: null, message: null));
    try {
      Map<String, dynamic> health = const {};
      try {
        health = await repo.platformHealth();
      } catch (_) {}
      final listed = await repo.listServices();
      List<Map<String, dynamic>> configs = const [];
      try {
        configs = await executeRepo.listConfigs();
      } catch (_) {}

      final ordered = _orderServices(listed.ids);
      final prefer = initialService != null &&
              initialService.isNotEmpty &&
              ordered.contains(initialService)
          ? initialService
          : (ordered.contains('am-subscription')
              ? 'am-subscription'
              : (ordered.isEmpty ? null : ordered.first));

      // Paint full catalog immediately so slow /apis probes cannot hide services.
      emit(
        state.copyWith(
          loading: false,
          services: ordered,
          serviceLabels: listed.labels,
          configs: configs,
          health: health,
          selectedService: prefer,
          navMode: initialNavMode ?? SpecsNavMode.collections,
          workspaceTab: initialTab ?? SpecsWorkspaceTab.test,
          message: ordered.isEmpty ? 'No workspace services registered.' : null,
          error: null,
        ),
      );
      // ignore: unawaited_futures
      _ensureToken();
      if (prefer != null) {
        await selectService(prefer);
        // selectService already kicks tab/mode ensures; only hydrate deep-link version.
        if (state.navMode == SpecsNavMode.datasets &&
            initialPayloadVersion != null &&
            initialPayloadVersion.isNotEmpty) {
          await ensurePayloadVersion(initialPayloadVersion);
        }
      }
      // ignore: unawaited_futures
      _pruneEmptyServicesInBackground(
        ids: ordered,
        labels: listed.labels,
        env: state.environment,
      );
    } catch (e) {
      emit(
        state.copyWith(
          loading: false,
          error: e.toString(),
          message: 'Specs boot failed: $e',
        ),
      );
    }
  }

  void setNavMode(SpecsNavMode mode) {
    if (state.navMode == mode) return;
    emit(state.copyWith(navMode: mode));
    if (mode == SpecsNavMode.datasets) {
      // ignore: unawaited_futures
      ensurePayloadSetList();
    } else {
      // ignore: unawaited_futures
      ensureForWorkspaceTab(state.workspaceTab);
    }
  }

  void setWorkspaceTab(SpecsWorkspaceTab tab) {
    if (state.workspaceTab == tab) return;
    emit(state.copyWith(workspaceTab: tab));
    // ignore: unawaited_futures
    ensureForWorkspaceTab(tab);
  }

  void setCollectionQuery(String q) =>
      emit(state.copyWith(collectionQuery: q));

  void setCollectionRuntimeFilter(String v) =>
      emit(state.copyWith(collectionRuntimeFilter: v));

  void setCollectionFacet(String v) =>
      emit(state.copyWith(collectionFacet: v));

  void setResourceQuery(String q) => emit(state.copyWith(resourceQuery: q));

  void setResourceTypeFilter(String v) =>
      emit(state.copyWith(resourceTypeFilter: v));

  /// Tab/mode-scoped loader — only hits endpoints the active pane needs.
  Future<void> ensureForWorkspaceTab(SpecsWorkspaceTab tab) async {
    switch (tab) {
      case SpecsWorkspaceTab.test:
        await ensureApis();
        await ensureTestDraft();
      case SpecsWorkspaceTab.swagger:
        await ensureOpenapiDoc();
      case SpecsWorkspaceTab.mcp:
        await ensureMcpTools();
      case SpecsWorkspaceTab.sdk:
        await ensureApis();
        if (state.mcpTools.isEmpty) await ensureMcpTools();
        if (state.openapiUrl == null) await ensureOpenapiDoc();
      case SpecsWorkspaceTab.usecases:
        await ensureOverview();
    }
  }

  Future<void> ensureApis({bool force = false}) async {
    final svc = state.selectedService;
    if (svc == null) return;
    if (state.apisLoading) return;
    if (!force && (_apisFetchedFor == svc || state.apis.isNotEmpty)) return;
    await selectService(svc);
  }

  Future<void> ensureTestDraft() async {
    final api = state.selectedApi;
    if (api == null) return;
    if (state.draft.path.isNotEmpty) return;
    await applyApiToDraft(api, pushHistory: false);
  }

  Future<void> ensureOpenapiDoc({bool force = false}) async {
    final svc = state.selectedService;
    if (svc == null) return;
    if (!force && state.openapiDoc != null) return;
    if (state.openapiLoading) return;
    final gen = _loadGen;
    emit(state.copyWith(openapiLoading: true));
    try {
      await _loadOpenapiDoc(svc);
    } finally {
      if (_loadGen == gen && state.selectedService == svc) {
        emit(state.copyWith(openapiLoading: false));
      }
    }
  }

  Future<void> ensureMcpTools({bool force = false}) async {
    final svc = state.selectedService;
    if (svc == null) return;
    if (!force && state.mcpTools.isNotEmpty) return;
    if (state.mcpLoading) return;
    final gen = _loadGen;
    emit(state.copyWith(mcpLoading: true));
    try {
      await refreshOpenapiTools();
    } catch (e) {
      if (_loadGen == gen && state.selectedService == svc) {
        emit(state.copyWith(message: 'OpenAPI tools unavailable: $e'));
      }
    } finally {
      if (_loadGen == gen && state.selectedService == svc) {
        emit(state.copyWith(mcpLoading: false));
      }
    }
  }

  Future<void> ensureOverview({bool force = false}) async {
    if (!force && state.overview != null) return;
    await loadOverview();
  }

  /// Version list only — does not hydrate rows until [ensurePayloadVersion].
  Future<void> ensurePayloadSetList({bool resetVersion = false}) async {
    final svc = state.selectedService;
    if (svc == null) return;
    if (state.payloadListLoading) return;
    if (!resetVersion && state.payloadSets.isNotEmpty) return;
    final gen = _loadGen;
    emit(state.copyWith(payloadListLoading: true));
    try {
      await _loadPayloadSets(svc, resetVersion: resetVersion, hydrate: false);
    } finally {
      if (_loadGen == gen && state.selectedService == svc) {
        emit(state.copyWith(payloadListLoading: false));
      }
    }
  }

  Future<void> ensurePayloadVersion(String? version) async {
    final svc = state.selectedService;
    if (svc == null || version == null || version.isEmpty) return;
    final gen = _loadGen;
    emit(
      state.copyWith(
        selectedPayloadVersion: version,
        payloadRowsLoading: true,
        clearPayloadApiIds: true,
      ),
    );
    await _hydrateDataFromSet(svc, version);
    if (_loadGen == gen && state.selectedService == svc) {
      emit(state.copyWith(payloadRowsLoading: false));
    }
  }

  Future<void> _loadPayloadSets(
    String service, {
    bool resetVersion = false,
    bool hydrate = true,
  }) async {
    try {
      final sets = await repo.payloadSets(service);
      if (state.selectedService != service) return;
      String? version;
      if (!resetVersion) {
        version = state.selectedPayloadVersion;
      }
      // Reset or pick active set for this service (only when hydrating rows).
      final versions = sets
          .map((s) => '${s['version'] ?? s['id'] ?? ''}')
          .where((v) => v.isNotEmpty)
          .toSet();
      if (version == null || !versions.contains(version) || resetVersion) {
        version = null;
        if (hydrate && sets.isNotEmpty) {
          final active = sets.firstWhere(
            (s) => s['active'] == true || s['is_active'] == true,
            orElse: () => sets.first,
          );
          version = '${active['version'] ?? active['id'] ?? ''}';
          if (version.isEmpty) version = null;
        }
      }
      emit(
        state.copyWith(
          payloadSets: sets,
          selectedPayloadVersion: version,
          clearPayloadVersion: version == null,
          clearPayloadApiIds: true,
          clearGenerate: !hydrate,
        ),
      );
      if (!hydrate) return;
      await _hydrateDataFromSet(service, version);
      if (version != null && state.selectedApiId != null) {
        await loadSetApiIntoTry(pushHistory: false);
      }
    } catch (_) {
      if (state.selectedService != service) return;
      emit(state.copyWith(
        payloadSets: const [],
        clearPayloadVersion: true,
        clearGenerate: true,
      ));
    }
  }

  /// Map payload-set file entries into Data tab rows (survives refresh).
  Future<void> _hydrateDataFromSet(String service, String? version) async {
    if (version == null || version.isEmpty) {
      if (state.generateResults.isEmpty) {
        emit(state.copyWith(clearGenerate: true));
      }
      return;
    }
    // Don't wipe a fresh generate-all result for the same version.
    final summaryVer = '${state.generateSummary?['payload_set_version'] ?? ''}';
    if (state.generateResults.isNotEmpty &&
        state.generateSummary?['from_generate'] == true &&
        summaryVer == version) {
      return;
    }
    try {
      final set = await repo.getPayloadSet(service, version);
      final apis = set['apis'];
      if (apis is! Map) {
        emit(state.copyWith(clearGenerate: true));
        return;
      }
      final rows = <Map<String, dynamic>>[];
      for (final e in apis.entries) {
        final entry = e.value;
        if (entry is! Map) continue;
        final m = Map<String, dynamic>.from(entry);
        final req = m['request'] is Map
            ? Map<String, dynamic>.from(m['request'] as Map)
            : <String, dynamic>{
                'method': m['method'],
                'path': m['path'],
                'query': m['query'],
                'path_params': m['path_params'],
                'body': m['body'],
                'headers': m['headers'],
              };
        final resp = m['response'] is Map
            ? Map<String, dynamic>.from(m['response'] as Map)
            : null;
        final status = resp?['status'] ?? resp?['status_code'];
        final statusInt = status is num ? status.toInt() : int.tryParse('$status');
        final ok = statusInt != null && statusInt >= 200 && statusInt < 300;
        final meta = m['meta'] is Map ? Map<String, dynamic>.from(m['meta'] as Map) : {};
        rows.add({
          'api_id': m['api_id'] ?? e.key,
          'method': '${req['method'] ?? m['method'] ?? 'GET'}'.toUpperCase(),
          'path': '${req['path'] ?? m['path'] ?? ''}',
          'name': meta['name'] ?? m['name'],
          'ok': ok || statusInt == null,
          'final_status': statusInt,
          'source': meta['source'] ?? 'set',
          'attempts_used': 1,
          'attempts': const [],
          'request': req,
          'response': resp == null
              ? null
              : {
                  'status_code': statusInt,
                  'body': resp['body'],
                  'error': resp['error'],
                },
          'error': null,
          'payload_set_version': int.tryParse(version),
          'from_set': true,
        });
      }
      rows.sort((a, b) {
        final pa = '${a['path']}';
        final pb = '${b['path']}';
        return pa.compareTo(pb);
      });
      emit(
        state.copyWith(
          generateResults: rows,
          generateSummary: {
            'total': rows.length,
            'passed': rows.where((r) => r['ok'] == true).length,
            'failed': rows.where((r) => r['ok'] != true).length,
            'payload_set_version': version,
            'from_file': true,
          },
          // Remount Swagger with examples from this payload set.
          specRevision: _specRevisionFor(
            service: service,
            docVersion: state.specRevision,
            pathCount: '${rows.length}',
            payloadVersion: version,
          ),
        ),
      );
    } catch (_) {
      // leave existing generate results
    }
  }

  /// OpenAPI document with `example` fields from the selected payload set.
  Map<String, dynamic>? swaggerSpecWithPayloadExamples() {
    return openapiDocWithPayloadExamples(
      state.openapiDoc,
      state.generateResults,
    );
  }

  String _specRevisionFor({
    required String service,
    required String docVersion,
    required String pathCount,
    String? payloadVersion,
  }) {
    final pv = payloadVersion ?? state.selectedPayloadVersion ?? '-';
    return '$service|${state.environment}|$docVersion|$pathCount|pv=$pv';
  }

  Future<void> selectService(String service) async {
    history.clear();
    final gen = ++_loadGen;
    _apisFetchedFor = null;
    emit(
      state.copyWith(
        apisLoading: true,
        selectedService: service,
        selectedApiIds: const {},
        apis: const [],
        payloadSets: const [],
        error: null,
        message: null,
        clearActionResult: true,
        clearTryResult: true,
        clearMcpSummary: true,
        clearMcpTools: true,
        clearMcpReport: true,
        clearCounts: true,
        clearOverview: true,
        clearGenerate: true,
        clearOpenapi: true,
        clearOpenapiUrl: true,
        clearTargetUrl: true,
        clearPayloadVersion: true,
        canRevert: false,
        fileBytes: const {},
        openapiLoading: false,
        mcpLoading: false,
        payloadListLoading: false,
        payloadRowsLoading: false,
        resourceQuery: '',
      ),
    );
    List<Map<String, dynamic>> apis = const [];
    try {
      // First-ready: paint APIs as soon as they arrive — no eager OpenAPI/tools/overview.
      apis = await repo.apis(service, environment: state.environment);
      if (_loadGen != gen || state.selectedService != service) return;
      _apisFetchedFor = service;
      final first = apis.isEmpty ? null : apis.first;
      final firstId = first == null ? null : apiId(first, 0);
      emit(
        state.copyWith(
          apisLoading: false,
          apis: apis,
          selectedApiId: firstId,
          draft: TryDraft(authBearer: state.tryToken),
          error: null,
          message: apis.isEmpty
              ? 'No APIs yet — OpenAPI sync may still be pending for this env.'
              : null,
          clearPayloadDiff: true,
          clearParamEnums: true,
        ),
      );

      // Tab/mode-scoped body loads; MCP tools for secondary rail are first-ready (non-blocking).
      if (state.navMode == SpecsNavMode.datasets) {
        // ignore: unawaited_futures
        ensurePayloadSetList(resetVersion: true);
      } else {
        // ignore: unawaited_futures
        ensureMcpTools();
        // ignore: unawaited_futures
        ensureForWorkspaceTab(state.workspaceTab);
      }
    } catch (e) {
      if (_loadGen != gen || state.selectedService != service) return;
      _apisFetchedFor = service;
      emit(
        state.copyWith(
          apisLoading: false,
          apis: apis,
          error: e.toString(),
          message: 'Failed to load APIs for $service: $e',
        ),
      );
    }
  }

  Future<void> _loadOpenapiDoc(String service) async {
    try {
      final docEnvelope =
          await repo.openapi(service, environment: state.environment);
      if (state.selectedService != service) return;
      final doc = _stableDoc(docEnvelope);
      final target =
          '${docEnvelope['target_url'] ?? docEnvelope['resolved_target'] ?? ''}'
              .trim();
      final rev = _specRevisionFor(
        service: service,
        docVersion: '${docEnvelope['version'] ?? ''}',
        pathCount:
            '${docEnvelope['path_count'] ?? doc?['paths']?.length ?? 0}',
      );
      final ops = docEnvelope['operation_count'];
      emit(
        state.copyWith(
          openapi: docEnvelope,
          openapiDoc: doc,
          openapiUrl: _extractOpenapiUrl(docEnvelope),
          targetUrl: target.isEmpty ? null : target,
          clearTargetUrl: target.isEmpty,
          specRevision: rev,
          operationCount: ops is num ? ops.toInt() : null,
        ),
      );
    } catch (e) {
      if (state.selectedService == service) {
        emit(state.copyWith(message: 'OpenAPI doc unavailable: $e'));
      }
    }
  }

  Future<void> refreshOpenapiTools() async {
    final svc = state.selectedService;
    if (svc == null) return;
    final out = await repo.openapiTools(svc, environment: state.environment);
    if (state.selectedService != svc) return;
    final tools = mapList(out, keys: const ['tools', 'items']);
    final ops = out['operation_count'];
    final count = out['count'];
    emit(
      state.copyWith(
        mcpTools: tools,
        toolsCount: count is num ? count.toInt() : tools.length,
        operationCount: ops is num ? ops.toInt() : state.operationCount,
      ),
    );
  }

  Future<void> loadOverview() async {
    final svc = state.selectedService;
    if (svc == null) return;
    emit(state.copyWith(overviewLoading: true));
    try {
      // Cached overview first — live OpenAPI fan-out is slow and blocks Use cases.
      final ov = await repo.overview(
        svc,
        environment: state.environment,
        liveOpenapi: false,
      );
      if (state.selectedService != svc) return;
      emit(state.copyWith(overviewLoading: false, overview: ov));
    } catch (e) {
      if (state.selectedService != svc) return;
      emit(
        state.copyWith(
          overviewLoading: false,
          message: 'Use cases overview unavailable: $e',
        ),
      );
    }
  }

  Future<void> generateAllPayloads() async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    emit(
      state.copyWith(
        generating: true,
        clearGenerate: true,
        message: 'Generating payloads for ${state.apis.length} APIs…',
      ),
    );
    try {
      final out = await repo.generateAllPayloads(
        service: svc,
        environment: state.environment,
      );
      final rows = mapList(out, keys: const ['results', 'items']);
      await _loadPayloadSets(svc, resetVersion: false);
      final verOut = out['payload_set_version'];
      emit(
        state.copyWith(
          generating: false,
          generateResults: rows,
          generateSummary: {
            'total': out['total'],
            'passed': out['passed'],
            'failed': out['failed'],
            'payload_set_version': verOut,
            'from_generate': true,
          },
          selectedPayloadVersion:
              verOut != null ? '$verOut' : state.selectedPayloadVersion,
          message:
              'Data prep done: ${out['passed'] ?? 0} passed / ${out['failed'] ?? 0} failed'
              ' (set v${verOut ?? '?'})',
        ),
      );
    } catch (e) {
      emit(
        state.copyWith(
          generating: false,
          message: 'Generate-all failed: $e',
        ),
      );
    }
  }

  /// Start Specs onboard prep workflow; polls until steps[] report is ready.
  Future<void> startOnboardPrep() async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    emit(
      state.copyWith(
        onboarding: true,
        clearOnboard: true,
        message: 'Starting onboard prep for $svc…',
      ),
    );
    try {
      final started = await repo.startOnboard(
        service: svc,
        environment: state.environment,
        allowLlm: true,
        wait: false,
      );
      final wfId = '${started['workflow_id'] ?? ''}';
      Map<String, dynamic>? report = started['result'] is Map
          ? Map<String, dynamic>.from(started['result'] as Map)
          : null;
      if (report == null && wfId.isNotEmpty) {
        for (var i = 0; i < 90; i++) {
          await Future<void>.delayed(const Duration(seconds: 2));
          final polled = await repo.onboardStatus(
            service: svc,
            workflowId: wfId,
          );
          final status = '${polled['status'] ?? ''}';
          if (polled['result'] is Map) {
            report = Map<String, dynamic>.from(polled['result'] as Map);
            break;
          }
          if (status == 'FAILED' ||
              status == 'TERMINATED' ||
              status == 'CANCELED' ||
              status == 'TIMED_OUT') {
            emit(
              state.copyWith(
                onboarding: false,
                onboardWorkflowId: wfId,
                message: 'Onboard prep $status',
              ),
            );
            return;
          }
        }
      }
      report ??= await repo.onboardLatest(
        service: svc,
        environment: state.environment,
      );
      final steps = report?['steps'];
      final failed = report?['failed_step'];
      final ok = report?['ok'] == true;
      final n = steps is List ? steps.length : 0;
      emit(
        state.copyWith(
          onboarding: false,
          onboardWorkflowId: wfId.isEmpty ? null : wfId,
          onboardReport: report,
          message: ok
              ? 'Onboard prep ok ($n steps)${wfId.isNotEmpty ? ' · $wfId' : ''}'
              : 'Onboard prep failed at ${failed ?? '?'} ($n steps)'
                  '${wfId.isNotEmpty ? ' · $wfId' : ''}',
        ),
      );
      if (ok) {
        await selectService(svc);
      }
    } catch (e) {
      emit(
        state.copyWith(
          onboarding: false,
          message: 'Onboard prep failed: $e',
        ),
      );
    }
  }

  Future<void> importPostmanCollection({
    required Map<String, dynamic> collection,
    Map<String, dynamic>? environment,
  }) async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    emit(state.copyWith(generating: true, message: 'Importing collection…'));
    try {
      final out = await repo.importCollection(
        service: svc,
        collection: collection,
        environment: environment,
        format: 'postman',
      );
      final ver = '${out['payload_set_version'] ?? ''}';
      await _loadPayloadSets(svc, resetVersion: true);
      if (ver.isNotEmpty) {
        await setPayloadVersion(ver);
      }
      emit(
        state.copyWith(
          generating: false,
          message:
              'Imported ${out['imported'] ?? 0} requests → set v${out['payload_set_version'] ?? '?'}'
              '${(out['warnings'] is List && (out['warnings'] as List).isNotEmpty) ? ' (${(out['warnings'] as List).length} warnings)' : ''}',
        ),
      );
    } catch (e) {
      emit(state.copyWith(generating: false, message: 'Import failed: $e'));
    }
  }

  /// Import a .zip / .gz / large JSON pack via multipart (compressed on the wire).
  Future<void> importPayloadZip({
    required List<int> bytes,
    required String filename,
  }) async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    emit(
      state.copyWith(
        generating: true,
        message: 'Importing ${filename} (${bytes.length} bytes)…',
      ),
    );
    try {
      final out = await repo.importPayloadZip(
        service: svc,
        bytes: bytes,
        filename: filename,
      );
      final ver = '${out['payload_set_version'] ?? ''}';
      await _loadPayloadSets(svc, resetVersion: true);
      if (ver.isNotEmpty) {
        await setPayloadVersion(ver);
      }
      final xfer = out['transfer'] is Map
          ? Map<String, dynamic>.from(out['transfer'] as Map)
          : null;
      emit(
        state.copyWith(
          generating: false,
          message:
              'Imported ${out['imported'] ?? 0} → set v${out['payload_set_version'] ?? '?'}'
              '${xfer != null ? ' · ${xfer['encoding']} ${xfer['bytes_in']}B' : ''}',
        ),
      );
    } catch (e) {
      emit(state.copyWith(generating: false, message: 'Zip import failed: $e'));
    }
  }

  Future<List<int>?> exportPayloadZip() async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    if (svc == null || ver == null) {
      emit(state.copyWith(message: 'Select a service and payload version'));
      return null;
    }
    try {
      final bytes = await repo.exportPayloadSetZip(service: svc, version: ver);
      emit(
        state.copyWith(
          message: 'Exported $svc v$ver zip (${bytes.length} bytes)',
        ),
      );
      return bytes;
    } catch (e) {
      emit(state.copyWith(message: 'Export zip failed: $e'));
      return null;
    }
  }

  /// Open compressed export in the browser (same-origin download).
  Future<void> downloadPayloadZip() async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    if (svc == null || ver == null) {
      emit(state.copyWith(message: 'Select a service and payload version'));
      return;
    }
    try {
      final cfg = getIt.isRegistered<PortalConfig>()
          ? getIt<PortalConfig>()
          : null;
      final base = (cfg?.apiBase ?? '/qa').replaceAll(RegExp(r'/$'), '');
      final uri = Uri.parse('$base/api/payload-sets/$svc/$ver/export.zip');
      final ok = await launchUrl(uri, webOnlyWindowName: '_blank');
      emit(
        state.copyWith(
          message: ok
              ? 'Downloading $svc v$ver.zip'
              : 'Could not open export URL',
        ),
      );
    } catch (e) {
      emit(state.copyWith(message: 'Export zip failed: $e'));
    }
  }

  Future<void> pickTool(Map<String, dynamic> tool) async {
    final method = '${tool['method'] ?? ''}'.toUpperCase();
    final path = '${tool['path'] ?? ''}'.trim();
    final apiIdHint = '${tool['api_id'] ?? tool['op_id'] ?? ''}'.trim();
    Map<String, dynamic>? match;
    for (var i = 0; i < state.apis.length; i++) {
      final api = state.apis[i];
      final id = apiId(api, i);
      final apiMethod = '${api['method'] ?? ''}'.toUpperCase();
      final apiPath = '${api['path'] ?? api['path_template'] ?? ''}'.trim();
      final tpl = '${api['path_template'] ?? ''}'.trim();
      if (apiIdHint.isNotEmpty &&
          (id == apiIdHint ||
              '${api['operation_id'] ?? api['operationId'] ?? ''}' == apiIdHint)) {
        match = api;
        break;
      }
      if (apiMethod == method &&
          (apiPath == path || tpl == path || apiPath.contains(path) || path.contains(apiPath))) {
        match = api;
        break;
      }
    }
    if (match != null) {
      await pickApi(match);
      return;
    }
    emit(
      state.copyWith(
        draft: state.draft.copyWith(method: method.isEmpty ? 'GET' : method, path: path),
        message: 'Tool loaded into Test (no matching API row)',
      ),
    );
  }

  Future<void> setEnvironment(String env) async {
    emit(
      state.copyWith(
        environment: env,
        clearOverview: true,
        clearGenerate: true,
        clearTryToken: true,
      ),
    );
    // Dig/dev must not keep a prod JWT (JWKS kid mismatch → subscription 500).
    await _ensureToken(force: true);
    try {
      final listed = await repo.listServices();
      final ordered = _orderServices(listed.ids);
      var pick = state.selectedService;
      if (pick == null || !ordered.contains(pick)) {
        pick = ordered.contains('am-subscription')
            ? 'am-subscription'
            : (ordered.isEmpty ? null : ordered.first);
      }
      emit(
        state.copyWith(
          services: ordered,
          serviceLabels: listed.labels,
          selectedService: pick,
          message: ordered.isEmpty ? 'No workspace services registered.' : null,
        ),
      );
      if (pick != null) {
        // ignore: unawaited_futures
        selectService(pick);
      }
      // ignore: unawaited_futures
      _pruneEmptyServicesInBackground(
        ids: ordered,
        labels: listed.labels,
        env: env,
      );
    } catch (_) {
      final svc = state.selectedService;
      if (svc != null) {
        // ignore: unawaited_futures
        selectService(svc);
      }
    }
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

  /// Load set payload for selected API + version, then Send (single-click Test).
  Future<void> testApiOneClick([Map<String, dynamic>? api]) async {
    if (api != null) {
      await pickApi(api);
    } else if (state.selectedApiId != null) {
      final match = state.selectedApi;
      if (match != null) await applyApiToDraft(match, pushHistory: false);
      await loadSetApiIntoTry(pushHistory: false);
    }
    await runTry();
  }

  /// Test all checked APIs using the active payload set version.
  Future<void> testCheckedApis() async {
    final ids = state.selectedApiIds.isNotEmpty
        ? state.selectedApiIds.toList()
        : (state.selectedApiId != null ? [state.selectedApiId!] : <String>[]);
    if (ids.isEmpty) {
      emit(state.copyWith(message: 'Select at least one API to test'));
      return;
    }
    final lines = <String>[];
    var passed = 0;
    for (final id in ids) {
      Map<String, dynamic>? api;
      for (var i = 0; i < state.apis.length; i++) {
        if (apiId(state.apis[i], i) == id) {
          api = state.apis[i];
          break;
        }
      }
      if (api == null) {
        lines.add('$id — not found');
        continue;
      }
      await pickApi(api);
      await runTry();
      final code = state.tryStatusCode;
      final ok = code != null && code >= 200 && code < 300;
      if (ok) passed += 1;
      lines.add(
        '${ok ? 'PASS' : 'FAIL'} ${state.draft.method} ${state.draft.path} HTTP ${code ?? '—'}',
      );
    }
    emit(
      state.copyWith(
        actionResult: lines.join('\n'),
        message: 'Tested ${ids.length}: $passed passed',
      ),
    );
  }

  /// Run Use cases via execute config and return run id for navigation.
  Future<String?> runUseCases() async {
    return runLoad(mockOne: false);
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
    final svc = state.selectedService;
    emit(
      state.copyWith(
        selectedPayloadVersion: version,
        clearPayloadVersion: version == null,
        payloadRowsLoading: version != null && version.isNotEmpty,
        clearGenerate: version == null,
        specRevision: _specRevisionFor(
          service: svc ?? state.selectedService ?? 'none',
          docVersion: state.specRevision,
          pathCount: '${state.generateResults.length}',
          payloadVersion: version ?? '-',
        ),
      ),
    );
    if (svc != null && version != null && version.isNotEmpty) {
      await ensurePayloadVersion(version);
    } else if (svc != null) {
      emit(state.copyWith(payloadRowsLoading: false));
    }
    final api = state.selectedApi;
    if (api != null && state.navMode == SpecsNavMode.collections) {
      await applyApiToDraft(api, pushHistory: false);
    }
    if (version != null) {
      await loadSetApiIntoTry(pushHistory: false);
    } else if (api != null) {
      emit(state.copyWith(message: 'Payload version cleared — using OpenAPI examples'));
    }
  }

  Map<String, dynamic>? _findSetEntry(
    Map apis, {
    required String apiId,
    String? method,
    String? path,
  }) {
    dynamic entry = apis[apiId] ?? apis[apiId.replaceAll('.', '_')];
    if (entry is Map) return Map<String, dynamic>.from(entry);
    final lower = apiId.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
    for (final e in apis.entries) {
      final k = '${e.key}'.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
      if (k == lower && e.value is Map) {
        return Map<String, dynamic>.from(e.value as Map);
      }
    }
    final m = (method ?? '').toUpperCase();
    final p = (path ?? '').trim();
    if (m.isEmpty || p.isEmpty) return null;
    for (final e in apis.entries) {
      if (e.value is! Map) continue;
      final row = Map<String, dynamic>.from(e.value as Map);
      final req = row['request'] is Map
          ? Map<String, dynamic>.from(row['request'] as Map)
          : row;
      final rm = '${req['method'] ?? ''}'.toUpperCase();
      final rp = '${req['path'] ?? ''}'.trim();
      if (rm == m && (rp == p || rp.endsWith(p) || p.endsWith(rp))) {
        return row;
      }
    }
    return null;
  }

  Future<void> loadSetApiIntoTry({bool pushHistory = true}) async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    final id = state.selectedApiId;
    if (svc == null || ver == null || id == null) return;
    try {
      final set = await repo.getPayloadSet(svc, ver);
      final apis = set['apis'];
      if (apis is! Map) {
        emit(state.copyWith(message: 'Payload set v$ver has no APIs'));
        return;
      }
      final selected = state.selectedApi;
      final method = '${selected?['method'] ?? state.draft.method}'.toUpperCase();
      final path = '${selected?['path'] ?? selected?['path_template'] ?? state.draft.path}';
      final entry = _findSetEntry(apis, apiId: id, method: method, path: path);
      if (entry != null) {
        applyPayloadMap(entry, pushHistory: pushHistory);
        emit(state.copyWith(message: 'Loaded payload from set v$ver'));
      } else {
        emit(
          state.copyWith(
            message: 'No payload in v$ver for $method $path ($id)',
          ),
        );
      }
    } catch (e) {
      emit(state.copyWith(message: 'Failed to load set v$ver: $e'));
    }
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
      final prev = history.pop();
      if (prev != null) {
        emit(state.copyWith(
          draft: prev,
          canRevert: history.canRevert,
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
    // Checked APIs win. Otherwise load/all-suites = entire OpenAPI catalog for
    // the service (null api_ids). Rail highlight alone must not shrink a load run
    // to one op (that caused api_count=1 on /health while Specs showed 19 APIs).
    List<String>? ids;
    if (state.selectedApiIds.isNotEmpty) {
      ids = state.selectedApiIds.toList();
    } else if (mockOne) {
      final one = state.selectedApiId;
      if (one != null && one.isNotEmpty) {
        ids = [one];
      } else if (state.apis.isNotEmpty) {
        ids = [apiId(state.apis.first, 0)];
      }
    } else {
      ids = null; // all OpenAPI ops for service
    }
    if (mockOne && (ids == null || ids.isEmpty)) {
      emit(state.copyWith(message: 'No APIs to run for $svc'));
      return null;
    }
    if (!mockOne && state.apis.isEmpty) {
      emit(state.copyWith(message: 'No OpenAPI APIs loaded for $svc'));
      return null;
    }
    final cfg = _matchConfig(svc, state.environment);
    final configId = cfg == null ? '' : '${cfg['id'] ?? ''}';
    emit(state.copyWith(loading: true, message: null));
    try {
      // Prefer exact config when present; else template profile + service bind.
      final out = await executeRepo.execute(
        configId: configId.isNotEmpty ? configId : null,
        service: svc,
        audience: 'developer',
        environment: state.environment,
        testType: 'k6',
        profile: mockOne ? 'debug' : 'load',
        vus: mockOne ? 1 : 20,
        calls: mockOne ? 1 : 50,
        apiIds: ids,
        openapiVersion: _openapiVersion(),
        payloadSet: state.selectedPayloadVersion,
      );
      final runId = '${out['id'] ?? out['run_id'] ?? ''}';
      emit(state.copyWith(loading: false, message: mockOne ? 'Mock 1× started' : 'Load started'));
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
      final out = await repo.ensurePayloadSet(svc);
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
      final out = await repo.activatePayloadSet(svc, version);
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

  void togglePayloadApiSelection(String apiId, {required bool selected}) {
    final next = {...state.selectedPayloadApiIds};
    if (selected) {
      next.add(apiId);
    } else {
      next.remove(apiId);
    }
    emit(state.copyWith(selectedPayloadApiIds: next));
  }

  void selectAllPayloadApis(Iterable<String> apiIds) {
    emit(state.copyWith(selectedPayloadApiIds: apiIds.toSet()));
  }

  void clearPayloadApiSelection() =>
      emit(state.copyWith(clearPayloadApiIds: true));

  Future<void> editPayloadSetApi({
    required String apiId,
    required Map<String, dynamic> request,
    Map<String, dynamic>? response,
    Map<String, dynamic>? meta,
    String name = 'working',
  }) async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    if (svc == null || ver == null) {
      emit(state.copyWith(message: 'Select a service and payload version'));
      return;
    }
    final verInt = int.tryParse(ver);
    if (verInt == null) {
      emit(state.copyWith(message: 'Invalid payload version'));
      return;
    }
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await repo.upsertPayloadSetApi(
        service: svc,
        apiId: apiId,
        version: verInt,
        request: request,
        response: response,
        meta: meta,
        name: name,
        bumpSet: false,
      );
      await _loadPayloadSets(svc);
      emit(state.copyWith(
        loading: false,
        actionResult: _prettyJson(out),
        message: 'Updated $apiId in v$ver',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString(), message: '$e'));
    }
  }

  Future<void> deleteSelectedPayloadApis() async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    final ids = state.selectedPayloadApiIds.toList();
    if (svc == null || ver == null || ids.isEmpty) {
      emit(state.copyWith(message: 'Select APIs to delete'));
      return;
    }
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await repo.deletePayloadSetApis(
        service: svc,
        version: ver,
        apiIds: ids,
      );
      await _loadPayloadSets(svc);
      emit(state.copyWith(
        loading: false,
        clearPayloadApiIds: true,
        actionResult: _prettyJson(out),
        message: 'Removed ${ids.length} API(s) from v$ver',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString(), message: '$e'));
    }
  }

  Future<void> deleteSelectedPayloadVersion() async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    if (svc == null || ver == null) {
      emit(state.copyWith(message: 'Select a payload version to delete'));
      return;
    }
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await repo.deletePayloadSet(service: svc, version: ver);
      await _loadPayloadSets(svc, resetVersion: true);
      emit(state.copyWith(
        loading: false,
        clearPayloadApiIds: true,
        actionResult: _prettyJson(out),
        message: 'Deleted payload set v$ver',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString(), message: '$e'));
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
      final out = await repo.savePayload(
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
      final out = await repo.buildPayload(
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
      final out = await repo.ensureWorking(
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
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    emit(state.copyWith(loading: true, clearMcpSummary: true));
    try {
      final out = await repo.prepareMcp(service: svc, environment: state.environment);
      await _loadPayloadSets(svc);
      try {
        await refreshOpenapiTools();
      } catch (_) {}
      emit(state.copyWith(
        loading: false,
        mcpSummary: {
          'mapped_count': out['mapped_count'],
          'skipped_count': out['skipped_count'],
          'mapped': out['mapped'],
          'skipped': out['skipped'],
          'portfolio_id': out['portfolio_id'],
        },
        message: 'MCP prepare done (${out['mapped_count'] ?? 0} mapped)',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, message: 'Prepare MCP failed: $e'));
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
      final res = await dio.request<dynamic>(
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

