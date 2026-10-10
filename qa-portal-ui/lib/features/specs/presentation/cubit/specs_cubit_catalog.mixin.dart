import '../../../../core/di/injection.dart';
import '../../../../core/network/json_lists.dart';
import '../../domain/openapi_fill.dart';
import '../../domain/try_draft.dart';
import 'specs_cubit_host.mixin.dart';
import 'specs_profile_defaults.dart';
import 'specs_state.dart';

mixin SpecsCubitCatalogMixin on SpecsCubitHost {
  bool serviceHasRealApis(List<Map<String, dynamic>> apis) {
    final real = apis.where((a) {
      final aid = '${a['id'] ?? ''}';
      return aid != 'health-fallback' && !aid.endsWith('.health-fallback');
    }).toList();
    if (real.isNotEmpty || apis.length > 1) return true;
    if (apis.isEmpty) return false;
    final only = '${apis.first['id'] ?? ''}';
    return only != 'health-fallback';
  }

  List<String> orderServices(Iterable<String> ids) {
    final kept = ids.toList()..sort();
    if (kept.contains('am-subscription')) {
      kept.remove('am-subscription');
      kept.insert(0, 'am-subscription');
    }
    return kept;
  }

  /// Show catalog immediately, then prune services that return a confirmed empty
  /// OpenAPI list. Timeouts/errors keep the service (slow sync must not hide it).
  Future<void> pruneEmptyServicesInBackground({
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
            if (!serviceHasRealApis(apis)) empty.add(id);
          } catch (_) {
            // Keep on timeout/error — e.g. am-subscription OpenAPI sync is slow.
          }
        }),
      );
      if (isClosed) return;
    }
    if (empty.isEmpty) return;
    final selected = state.selectedService;
    final kept = orderServices(
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

      final ordered = orderServices(listed.ids);
      // Profile defaults (Execute/Profiles) win over catalog prefer when pending.
      String? pendingEnv;
      String? pendingSvc;
      String? pendingVer;
      if (getIt.isRegistered<SpecsProfileDefaults>()) {
        final d = getIt<SpecsProfileDefaults>();
        if (d.pending) {
          pendingEnv = d.environment;
          pendingSvc = d.service;
          pendingVer = d.payloadVersion;
          d.clear();
        }
      }
      if (pendingEnv != null && pendingEnv.isNotEmpty) {
        emit(state.copyWith(environment: pendingEnv));
      }
      final preferSvc = pendingSvc != null &&
              pendingSvc.isNotEmpty &&
              ordered.contains(pendingSvc)
          ? pendingSvc
          : (initialService != null &&
                  initialService.isNotEmpty &&
                  ordered.contains(initialService)
              ? initialService
              : (ordered.contains('am-subscription')
                  ? 'am-subscription'
                  : (ordered.isEmpty ? null : ordered.first)));
      final deepLinkVer = initialPayloadVersion != null &&
              initialPayloadVersion.isNotEmpty
          ? initialPayloadVersion
          : pendingVer;

      // Paint full catalog immediately so slow /apis probes cannot hide services.
      emit(
        state.copyWith(
          loading: false,
          services: ordered,
          serviceLabels: listed.labels,
          configs: configs,
          health: health,
          selectedService: preferSvc,
          navMode: initialNavMode ?? SpecsNavMode.collections,
          workspaceTab: initialTab ?? SpecsWorkspaceTab.test,
          message: ordered.isEmpty ? 'No workspace services registered.' : null,
          error: null,
        ),
      );
      // ignore: unawaited_futures
      ensureToken();
      if (preferSvc != null) {
        await selectService(preferSvc);
        if (deepLinkVer != null && deepLinkVer.isNotEmpty) {
          await ensurePayloadVersion(deepLinkVer);
        }
      }
      // ignore: unawaited_futures
      pruneEmptyServicesInBackground(
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
  @override
  Future<void> ensureForWorkspaceTab(SpecsWorkspaceTab tab) async {
    await ensureWorkspacePayload();
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

  /// Load payload-set list + hydrate active/selected version for OpenAPI tabs.
  @override
  Future<void> ensureWorkspacePayload() async {
    final svc = state.selectedService;
    if (svc == null) return;
    if (state.payloadListLoading || state.payloadRowsLoading) return;
    if (state.payloadSets.isEmpty) {
      await loadPayloadSets(svc, resetVersion: false, hydrate: true);
      return;
    }
    if (state.selectedPayloadVersion == null) {
      await loadPayloadSets(svc, resetVersion: false, hydrate: true);
      return;
    }
    if (state.generateResults.isEmpty) {
      await ensurePayloadVersion(state.selectedPayloadVersion);
    }
  }

  /// Apply env / service / dataset version from a selected Execute/Profiles config.
  @override
  Future<void> applyProfileDefaults({
    String? environment,
    String? service,
    String? payloadVersion,
  }) async {
    final env = (environment ?? '').trim();
    final svc = (service ?? '').trim();
    final ver = (payloadVersion ?? '').trim();
    if (env.isNotEmpty && env != state.environment) {
      emit(
        state.copyWith(
          environment: env,
          clearOverview: true,
          clearGenerate: true,
          clearTryToken: true,
        ),
      );
      await ensureToken(force: true);
    }
    if (svc.isNotEmpty && svc != state.selectedService) {
      await selectService(svc);
    } else if (state.selectedService != null && state.payloadSets.isEmpty) {
      await loadPayloadSets(
        state.selectedService!,
        resetVersion: false,
        hydrate: ver.isEmpty,
      );
    }
    if (ver.isNotEmpty) {
      await setPayloadVersion(ver);
    } else if (state.selectedPayloadVersion == null &&
        state.selectedService != null) {
      await loadPayloadSets(
        state.selectedService!,
        resetVersion: false,
        hydrate: true,
      );
    }
  }

  Future<void> ensureApis({bool force = false}) async {
    final svc = state.selectedService;
    if (svc == null) return;
    if (state.apisLoading) return;
    if (!force && (apisFetchedFor == svc || state.apis.isNotEmpty)) return;
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
    final gen = loadGen;
    emit(state.copyWith(openapiLoading: true));
    try {
      await loadOpenapiDoc(svc);
    } finally {
      if (loadGen == gen && state.selectedService == svc) {
        emit(state.copyWith(openapiLoading: false));
      }
    }
  }

  Future<void> ensureMcpTools({bool force = false}) async {
    final svc = state.selectedService;
    if (svc == null) return;
    if (!force && state.mcpTools.isNotEmpty) return;
    if (state.mcpLoading) return;
    final gen = loadGen;
    emit(state.copyWith(mcpLoading: true));
    try {
      await refreshOpenapiTools();
    } catch (e) {
      if (loadGen == gen && state.selectedService == svc) {
        emit(state.copyWith(message: 'OpenAPI tools unavailable: $e'));
      }
    } finally {
      if (loadGen == gen && state.selectedService == svc) {
        emit(state.copyWith(mcpLoading: false));
      }
    }
  }

  Future<void> ensureOverview({bool force = false}) async {
    if (!force && state.overview != null) return;
    await loadOverview();
  }

  /// Version list only — does not hydrate rows until [ensurePayloadVersion].
  Map<String, dynamic>? swaggerSpecWithPayloadExamples() {
    return openapiDocWithPayloadExamples(
      state.openapiDoc,
      state.generateResults,
    );
  }

  String specRevisionFor({
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
    final gen = ++loadGen;
    apisFetchedFor = null;
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
        clearActivePayloadVersion: true,
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
      if (loadGen != gen || state.selectedService != service) return;
      apisFetchedFor = service;
      final first = apis.isEmpty ? null : apis.first;
      final firstId = first == null ? null : specsApiId(first, 0);
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

      // Load dataset versions first so OpenAPI tabs inherit active/selected version.
      // ignore: unawaited_futures
      () async {
        await loadPayloadSets(service, resetVersion: true, hydrate: true);
        if (loadGen != gen || state.selectedService != service) return;
        if (state.navMode == SpecsNavMode.datasets) {
          // Target URL for curl / quick-test on Datasets page.
          // ignore: unawaited_futures
          ensureOpenapiDoc();
        } else {
          // ignore: unawaited_futures
          ensureMcpTools();
          // ignore: unawaited_futures
          ensureForWorkspaceTab(state.workspaceTab);
        }
      }();
    } catch (e) {
      if (loadGen != gen || state.selectedService != service) return;
      apisFetchedFor = service;
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

  Future<void> loadOpenapiDoc(String service) async {
    try {
      final docEnvelope =
          await repo.openapi(service, environment: state.environment);
      if (state.selectedService != service) return;
      final doc = stableDoc(docEnvelope);
      final target =
          '${docEnvelope['target_url'] ?? docEnvelope['resolved_target'] ?? ''}'
              .trim();
      final rev = specRevisionFor(
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
          openapiUrl: extractOpenapiUrl(docEnvelope),
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
    await ensureToken(force: true);
    try {
      final listed = await repo.listServices();
      final ordered = orderServices(listed.ids);
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
      pruneEmptyServicesInBackground(
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
}
