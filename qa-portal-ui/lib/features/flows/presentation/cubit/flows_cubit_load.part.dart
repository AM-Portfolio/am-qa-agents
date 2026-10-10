part of 'flows_cubit.dart';

extension FlowsCubitLoad on FlowsCubit {
  Future<void> load() async {
    emit(state.copyWith(loading: true, clearError: true));
    try {
      final page = await _repo.listFlowsPage(
        group: state.groupFilter.isEmpty ? null : state.groupFilter,
        category:
            state.categoryFilter.isEmpty ? null : state.categoryFilter,
        q: state.flowQuery.isEmpty ? null : state.flowQuery,
        apiPack: state.apiPackFilter.isEmpty ? null : state.apiPackFilter,
        limit: FlowsCubit._pageSize,
        offset: 0,
        facets: true,
      );
      final flows = (page['flows'] is List)
          ? (page['flows'] as List)
              .whereType<Map>()
              .map((e) => Map<String, dynamic>.from(e))
              .toList()
          : <Map<String, dynamic>>[];
      final total = page['total'] is int
          ? page['total'] as int
          : int.tryParse('${page['total']}') ?? flows.length;
      final facets = page['facets'] is Map
          ? Map<String, dynamic>.from(page['facets'] as Map)
          : null;
      final creds = await _repo.listCredentials();
      List<String> catalog = state.catalogServices;
      try {
        catalog = await _repo.listCatalogServices();
      } catch (_) {}
      final matched = _preferCredential(creds, state.env);
      final keepSelection = state.selectedFlowId != null &&
          flows.any((f) => '${f['id']}' == state.selectedFlowId);
      emit(
        state.copyWith(
          loading: false,
          flows: flows,
          flowsTotal: total,
          facets: facets,
          catalogServices: catalog,
          credentials: creds,
          credentialId: matched ?? state.credentialId,
          clearError: true,
        ),
      );
      if (keepSelection) {
        return;
      }
      if (flows.isNotEmpty) {
        await selectFlow('${flows.first['id']}');
      }
    } catch (e) {
      emit(state.copyWith(loading: false, error: friendlyApiError(e)));
    }
  }

  Future<void> loadMoreFlows() async {
    if (state.loadingMore || !state.hasMoreFlows) return;
    emit(state.copyWith(loadingMore: true));
    try {
      final page = await _repo.listFlowsPage(
        group: state.groupFilter.isEmpty ? null : state.groupFilter,
        category:
            state.categoryFilter.isEmpty ? null : state.categoryFilter,
        q: state.flowQuery.isEmpty ? null : state.flowQuery,
        apiPack: state.apiPackFilter.isEmpty ? null : state.apiPackFilter,
        limit: FlowsCubit._pageSize,
        offset: state.flows.length,
        facets: false,
      );
      final more = (page['flows'] is List)
          ? (page['flows'] as List)
              .whereType<Map>()
              .map((e) => Map<String, dynamic>.from(e))
              .toList()
          : <Map<String, dynamic>>[];
      final total = page['total'] is int
          ? page['total'] as int
          : state.flowsTotal;
      emit(
        state.copyWith(
          loadingMore: false,
          flows: [...state.flows, ...more],
          flowsTotal: total,
        ),
      );
    } catch (e) {
      emit(state.copyWith(loadingMore: false, error: friendlyApiError(e)));
    }
  }

  /// Fetch remaining pages until [flows] matches [flowsTotal] (capped).
  Future<void> loadAllFlows({int maxPages = 50}) async {
    var pages = 0;
    while (state.hasMoreFlows && pages < maxPages) {
      pages++;
      await loadMoreFlows();
      if (state.error != null) break;
    }
  }

  void setFlowQuery(String q) {
    emit(state.copyWith(flowQuery: q));
    _queryDebounce?.cancel();
    _queryDebounce = Timer(const Duration(milliseconds: 250), () {
      unawaited(load());
    });
  }

  void setGroupFilter(String group) {
    emit(state.copyWith(groupFilter: group));
    unawaited(load());
  }

  void setCategoryFilter(String category) {
    emit(state.copyWith(categoryFilter: category));
    unawaited(load());
  }

  void setApiPackFilter(String apiPack) {
    emit(state.copyWith(apiPackFilter: apiPack));
    unawaited(load());
  }

  Future<Map<String, dynamic>?> loadPayloadSet(
    String service, {
    int? version,
  }) {
    return _repo.getPayloadSet(service, version: version);
  }

  String? _preferCredential(List<Map<String, dynamic>> creds, String env) {
    if (creds.isEmpty) return null;
    final byEnv = creds.cast<Map<String, dynamic>?>().firstWhere(
          (c) => '${c?['env']}' == env,
          orElse: () => null,
        );
    if (byEnv != null) return '${byEnv['id']}';
    return '${creds.first['id']}';
  }

  Future<void> selectFlow(String flowId) async {
    emit(state.copyWith(
      selectedFlowId: flowId,
      clearExecution: true,
      clearRuntime: true,
      clearQuickResults: true,
      executing: false,
      graphDirty: false,
      execFilterFlowId: flowId,
    ));
    _poll?.cancel();
    try {
      final graph = await _repo.getGraph(flowId);
      final flowCred = graph['credential_id']?.toString();
      emit(
        state.copyWith(
          graph: graph,
          graphDirty: false,
          credentialId: (flowCred != null && flowCred.isNotEmpty)
              ? flowCred
              : state.credentialId,
          clearError: true,
        ),
      );
      await Future.wait([loadRuntime(), refreshExecutions()]);
    } catch (e) {
      emit(state.copyWith(error: friendlyApiError(e), graph: const {}));
    }
  }

  Future<void> quickTestNode(String nodeId) async {
    final fid = state.selectedFlowId;
    if (fid == null || state.isDraft) return;
    final testing = Map<String, Map<String, dynamic>>.from(state.nodeQuickResults);
    testing[nodeId] = {
      ...?testing[nodeId],
      'quickTesting': true,
    };
    emit(state.copyWith(nodeQuickResults: testing, selectedLogNodeId: nodeId));
    try {
      final vars = state.runtime?['variables'];
      final out = await _repo.quickTestNode(
        fid,
        nodeId,
        env: state.env,
        credentialId: state.credentialId,
        variables: vars is Map ? Map<String, dynamic>.from(vars) : null,
      );
      final next = Map<String, Map<String, dynamic>>.from(state.nodeQuickResults);
      next[nodeId] = {
        'quickTesting': false,
        'status': out['ok'] == true ? 'ok' : 'fail',
        'http_status': out['http_status'],
        'request': out['request'],
        'response': out['response'],
        'error': out['error'],
      };
      emit(state.copyWith(nodeQuickResults: next, clearError: true));
    } catch (e) {
      final next = Map<String, Map<String, dynamic>>.from(state.nodeQuickResults);
      next[nodeId] = {
        'quickTesting': false,
        'status': 'fail',
        'error': friendlyApiError(e),
      };
      emit(state.copyWith(nodeQuickResults: next, error: friendlyApiError(e)));
    }
  }

  void addNodeAfter(String afterNodeId, Map<String, dynamic> nodeStub) {
    final g = state.graph;
    if (g == null) return;
    final nodes = List<Map<String, dynamic>>.from(
      (g['nodes'] is List)
          ? (g['nodes'] as List).whereType<Map>().map((e) => Map<String, dynamic>.from(e))
          : const [],
    );
    final edges = List<Map<String, dynamic>>.from(
      (g['edges'] is List)
          ? (g['edges'] as List).whereType<Map>().map((e) => Map<String, dynamic>.from(e))
          : const [],
    );
    final prev = nodes.cast<Map<String, dynamic>?>().firstWhere(
          (n) => '${n?['id']}' == afterNodeId,
          orElse: () => null,
        );
    var newId = '${nodeStub['id'] ?? 'node_new'}';
    var n = 1;
    while (nodes.any((x) => '${x['id']}' == newId)) {
      newId = '${nodeStub['id']}_$n';
      n++;
    }
    final px = (prev?['x'] is num) ? (prev!['x'] as num).toDouble() : 80.0;
    final py = (prev?['y'] is num) ? (prev!['y'] as num).toDouble() : 120.0;
    final added = {
      ...nodeStub,
      'id': newId,
      'x': px + 260,
      'y': py,
    };
    nodes.add(added);
    edges.add({
      'id': '$afterNodeId->$newId',
      'from': afterNodeId,
      'to': newId,
      'optional': added['optional'] == true,
    });
    final nextGraph = Map<String, dynamic>.from(g)
      ..['nodes'] = nodes
      ..['edges'] = edges;
    emit(state.copyWith(graph: nextGraph, graphDirty: true));
  }

  void deleteNode(String nodeId) {
    if (nodeId == '__manual_trigger__') return;
    final g = state.graph;
    if (g == null) return;
    final nodes = List<Map<String, dynamic>>.from(
      (g['nodes'] is List)
          ? (g['nodes'] as List).whereType<Map>().map((e) => Map<String, dynamic>.from(e))
          : const [],
    )..removeWhere((n) => '${n['id']}' == nodeId);
    final edges = List<Map<String, dynamic>>.from(
      (g['edges'] is List)
          ? (g['edges'] as List).whereType<Map>().map((e) => Map<String, dynamic>.from(e))
          : const [],
    )..removeWhere(
        (e) => '${e['from']}' == nodeId || '${e['to']}' == nodeId,
      );
    final nextGraph = Map<String, dynamic>.from(g)
      ..['nodes'] = nodes
      ..['edges'] = edges;
    final quick = Map<String, Map<String, dynamic>>.from(state.nodeQuickResults)
      ..remove(nodeId);
    emit(
      state.copyWith(
        graph: nextGraph,
        graphDirty: true,
        nodeQuickResults: quick,
      ),
    );
  }

  Future<String?> saveGraph() async {
    final fid = state.selectedFlowId;
    final g = state.graph;
    if (fid == null || g == null) return null;
    final nodes = _persistableNodes(g);
    final edges = _persistableEdges(g);

    final isPack = fid.startsWith('pack:');
    final saveId = isPack
        ? 'AUTH_${fid.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_')}_${DateTime.now().millisecondsSinceEpoch % 100000}'
        : fid;
    final body = {
      'id': saveId,
      'title': g['title'] ?? saveId,
      'gate': g['gate'] ?? 'prod_safe',
      'group': g['group'] ?? 'other',
      'category': g['category'] ?? 'general',
      'description': g['description'] ?? '',
      'tags': g['tags'] ?? [],
      'created_by': 'authored',
      'api_pack': g['api_pack'],
      'credential_id': state.credentialId,
      'env_default': state.env,
      'variables': state.runtime?['variables'] ?? {},
      'payload_set_version': state.runtime?['payload_set_version'],
      'nodes': nodes,
      'edges': edges,
    };
    if (isPack) {
      await _repo.upsertFlow(body);
    } else {
      try {
        await _repo.updateFlow(saveId, body);
      } catch (_) {
        await _repo.upsertFlow(body);
      }
    }
    await load();
    await selectFlow(saveId);
    return saveId;
  }

  Future<List<Map<String, dynamic>>> listOpenApiTools(String service) {
    return _repo.listOpenApiTools(service, environment: state.env);
  }

  Future<List<String>> listCatalogServices() async {
    if (state.catalogServices.isNotEmpty) return state.catalogServices;
    final rows = await _repo.listCatalogServices();
    emit(state.copyWith(catalogServices: rows));
    return rows;
  }

  void setEnv(String env) {
    final matched = _preferCredential(state.credentials, env);
    emit(state.copyWith(env: env, credentialId: matched ?? state.credentialId));
  }

  void setCredentialId(String? id) => emit(state.copyWith(credentialId: id));

  void setBottomTab(int tab) => emit(state.copyWith(bottomTab: tab));

  void selectLogNode(String? nodeId) =>
      emit(state.copyWith(selectedLogNodeId: nodeId));
}
