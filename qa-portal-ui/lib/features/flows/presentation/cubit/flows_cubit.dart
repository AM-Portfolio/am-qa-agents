import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/flows_repository.dart';
import '../utils/flows_errors.dart';
import 'flows_state.dart';

class FlowsCubit extends Cubit<FlowsState> {
  FlowsCubit(this._repo) : super(const FlowsState());

  final FlowsRepository _repo;
  Timer? _poll;
  Timer? _queryDebounce;
  static const _pageSize = 100;

  Future<void> load() async {
    emit(state.copyWith(loading: true, clearError: true));
    try {
      final page = await _repo.listFlowsPage(
        group: state.groupFilter.isEmpty ? null : state.groupFilter,
        category:
            state.categoryFilter.isEmpty ? null : state.categoryFilter,
        q: state.flowQuery.isEmpty ? null : state.flowQuery,
        apiPack: state.apiPackFilter.isEmpty ? null : state.apiPackFilter,
        limit: _pageSize,
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
        limit: _pageSize,
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

  Future<void> loadRuntime() async {
    final fid = state.selectedFlowId;
    if (fid == null || fid.isEmpty) return;
    try {
      final rt = await _repo.getRuntime(fid);
      final envDef = rt['env_default']?.toString();
      final cred = rt['credential_id']?.toString();
      emit(
        state.copyWith(
          runtime: rt,
          env: (envDef != null && envDef.isNotEmpty) ? envDef : state.env,
          credentialId: (cred != null && cred.isNotEmpty) ? cred : state.credentialId,
        ),
      );
    } catch (e) {
      // Older agents may lack /runtime — keep UI usable
      emit(state.copyWith(runtime: {
        'flow_id': fid,
        'variables': <String, dynamic>{},
        'payload_sets': <dynamic>[],
        'error': friendlyApiError(e),
      }));
    }
  }

  Future<void> saveVariables(Map<String, dynamic> variables, {int? pinVersion}) async {
    final fid = state.selectedFlowId;
    if (fid == null) return;
    final rt = await _repo.setVariables(
      fid,
      variables: variables,
      payloadSetVersion: pinVersion,
    );
    emit(state.copyWith(runtime: rt));
  }

  Future<void> activatePayloadVersion(int version, {bool pin = true}) async {
    final fid = state.selectedFlowId;
    if (fid == null) return;
    final isPack = fid.startsWith('pack:');
    await _repo.setPayloadVersion(
      fid,
      version: version,
      activate: true,
      pinOnFlow: pin && !isPack,
    );
    await loadRuntime();
  }

  Future<void> refreshExecutions() async {
    try {
      final rows = await _repo.listExecutions(
        flowId: state.execFilterFlowId.isEmpty ? null : state.execFilterFlowId,
        env: state.execFilterEnv.isEmpty ? null : state.execFilterEnv,
        status: state.execFilterStatus.isEmpty ? null : state.execFilterStatus,
        limit: 40,
      );
      emit(state.copyWith(recentExecutions: rows));
    } catch (_) {
      emit(state.copyWith(recentExecutions: const []));
    }
  }

  void setExecFilter({String? status, String? flowId, String? env}) {
    emit(
      state.copyWith(
        execFilterStatus: status ?? state.execFilterStatus,
        execFilterFlowId: flowId ?? state.execFilterFlowId,
        execFilterEnv: env ?? state.execFilterEnv,
      ),
    );
    unawaited(refreshExecutions());
  }

  Future<void> openExecution(String executionId) async {
    _poll?.cancel();
    emit(state.copyWith(executionId: executionId, bottomTab: 0));
    await _pollExecution(executionId);
    final status = '${state.execution?['status'] ?? ''}';
    final done = {'finished', 'failed', 'error', 'stopped'}.contains(status);
    if (!done) {
      _poll = Timer.periodic(const Duration(milliseconds: 700), (_) {
        unawaited(_pollExecution(executionId));
      });
    }
  }

  Future<Map<String, dynamic>> loadExecutionObsLogs() async {
    final eid = state.executionId;
    if (eid == null || eid.isEmpty) {
      return {'available': false, 'reason': 'no_execution', 'lines': []};
    }
    return _repo.executionObsLogs(eid);
  }

  Future<List<Map<String, dynamic>>> suitePreview({
    String? group,
    String? apiPack,
    String? category,
  }) {
    return _repo.suitePreview(
      group: group,
      apiPack: apiPack,
      category: category,
    );
  }

  Future<Map<String, dynamic>> runSuite(List<String> flowIds) async {
    final out = await _repo.suiteExecute(
      flowIds: flowIds,
      env: state.env,
      credentialId: state.credentialId,
      payloadSetVersion: state.runtime?['selected_version'] is int
          ? state.runtime!['selected_version'] as int
          : int.tryParse('${state.runtime?['selected_version'] ?? ''}'),
      variables: (state.runtime?['variables'] is Map)
          ? Map<String, dynamic>.from(state.runtime!['variables'] as Map)
          : null,
    );
    final ids = out['execution_ids'];
    if (ids is List && ids.isNotEmpty) {
      await openExecution('${ids.first}');
    }
    await refreshExecutions();
    return out;
  }

  String? _autoSelectLogNode(
    Map<String, dynamic>? graph,
    Map nodes,
    String? current,
  ) {
    if (current != null && nodes.containsKey(current)) return current;
    final order = <String>[];
    final gNodes = graph?['nodes'];
    if (gNodes is List) {
      for (final raw in gNodes) {
        if (raw is Map) order.add('${raw['id']}');
      }
    }
    for (final id in order) {
      if (nodes.containsKey(id)) return id;
    }
    if (nodes.isEmpty) return null;
    return '${nodes.keys.first}';
  }

  Future<void> runSelected() async {
    final fid = state.selectedFlowId;
    if (fid == null || fid.isEmpty || state.isDraft) return;
    if (state.executing) return;
    emit(state.copyWith(executing: true, clearExecution: true, clearError: true, bottomTab: 0));
    try {
      final pin = state.runtime?['selected_version'];
      final vars = state.runtime?['variables'];
      final out = await _repo.execute(
        fid,
        env: state.env,
        credentialId: state.credentialId,
        variables: vars is Map ? Map<String, dynamic>.from(vars) : null,
        payloadSetVersion: pin is int ? pin : int.tryParse('$pin'),
      );
      final eid = out['execution_id']?.toString();
      if (eid == null || eid.isEmpty) {
        emit(state.copyWith(executing: false, error: 'no execution_id'));
        return;
      }
      emit(state.copyWith(executionId: eid));
      _poll?.cancel();
      _poll = Timer.periodic(const Duration(milliseconds: 700), (_) {
        unawaited(_pollExecution(eid));
      });
      await _pollExecution(eid);
    } catch (e) {
      emit(state.copyWith(executing: false, error: friendlyApiError(e)));
    }
  }

  Future<void> _pollExecution(String eid) async {
    try {
      final row = await _repo.getExecution(eid);
      final status = '${row['status'] ?? ''}';
      final done = {'finished', 'failed', 'error', 'stopped'}.contains(status);
      final nodes = row['nodes'];
      String? sel = state.selectedLogNodeId;
      if (nodes is Map && nodes.isNotEmpty) {
        sel = _autoSelectLogNode(state.graph, nodes, sel);
      }
      emit(
        state.copyWith(
          execution: row,
          executing: !done,
          selectedLogNodeId: sel,
          clearError: true,
        ),
      );
      if (done) {
        _poll?.cancel();
        unawaited(refreshExecutions());
      }
    } catch (e) {
      emit(state.copyWith(error: friendlyApiError(e), executing: false));
      _poll?.cancel();
    }
  }

  Future<void> stop() async {
    final eid = state.executionId;
    if (eid == null) return;
    await _repo.stopExecution(eid);
  }

  Future<void> saveCredential({
    required String name,
    required String username,
    required String password,
    String env = 'prod',
    String? id,
    String kind = 'identity_login',
    String? token,
    String baseUrl = '',
    String appId = '',
  }) async {
    final isToken = {
      'bearer_token',
      'llm_api_key',
      'api_key_header',
      'grafana_token',
      'prometheus_endpoint',
      'cliq_webhook',
      'temporal_endpoint',
    }.contains(kind);
    final optionalToken = {
      'prometheus_endpoint',
      'temporal_endpoint',
    }.contains(kind);
    await _repo.upsertCredential(
      {
        'name': name,
        'kind': kind,
        'env': env,
        'username': username,
        'base_url': baseUrl,
        if (appId.isNotEmpty) 'app_id': appId,
        if (!isToken && password.isNotEmpty) 'password': password,
        if (isToken && token != null && token.isNotEmpty) 'token': token,
        if (isToken && optionalToken && (token == null || token.isEmpty))
          'token': '',
      },
      id: id,
    );
    final creds = await _repo.listCredentials();
    emit(state.copyWith(credentials: creds));
  }

  Future<List<Map<String, dynamic>>> loadCredentialApps() =>
      _repo.listCredentialApps();

  Future<void> refreshCredentials() async {
    final creds = await _repo.listCredentials();
    emit(state.copyWith(credentials: creds));
  }

  Future<Map<String, dynamic>> probeCredential(String id) =>
      _repo.probeCredential(id);

  Future<Map<String, dynamic>> probeAllCredentials({String? env}) =>
      _repo.probeAllCredentials(env: env);

  Future<void> deleteCredential(String id) async {
    await _repo.deleteCredential(id);
    final creds = await _repo.listCredentials();
    final keep = creds.any((c) => '${c['id']}' == state.credentialId);
    emit(
      state.copyWith(
        credentials: creds,
        clearCredentialId: !keep,
        credentialId: keep ? state.credentialId : null,
      ),
    );
  }

  Future<Map<String, dynamic>> proposeScenarios({
    required String service,
    String? category,
  }) {
    String group = 'other';
    final s = service.toLowerCase();
    if (s.contains('identity')) {
      group = 'identity';
    } else if (s.contains('subscription')) {
      group = 'subscription';
    } else if (s.contains('market')) {
      group = 'market';
    }
    return _repo.proposeScenarios(
      service: service,
      group: group,
      category: category,
      env: state.env,
    );
  }

  void startDraftFlow() {
    _poll?.cancel();
    emit(
      state.copyWith(
        clearSelectedFlowId: true,
        clearExecution: true,
        clearRuntime: true,
        clearQuickResults: true,
        executing: false,
        graphDirty: true,
        graph: {
          'id': 'draft',
          'title': 'Untitled',
          'nodes': [
            {
              'id': '__manual_trigger__',
              'kind': 'manual_trigger',
              'label': 'Manual Trigger',
              'method': 'START',
              'path': 'click to run',
              'service': '',
              'x': 40.0,
              'y': 160.0,
            },
          ],
          'edges': <Map<String, dynamic>>[],
        },
      ),
    );
  }

  List<Map<String, dynamic>> _persistableNodes(Map<String, dynamic> g) {
    if (g['nodes'] is! List) return [];
    return (g['nodes'] as List)
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .where((n) {
          final kind = '${n['kind'] ?? ''}';
          final id = '${n['id'] ?? ''}';
          return kind != 'manual_trigger' &&
              kind != 'compose' &&
              id != '__manual_trigger__' &&
              id != '__compose_draft__';
        })
        .toList();
  }

  List<Map<String, dynamic>> _persistableEdges(Map<String, dynamic> g) {
    if (g['edges'] is! List) return [];
    return (g['edges'] as List)
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .where((e) {
          final from = '${e['from'] ?? ''}';
          final to = '${e['to'] ?? ''}';
          return from != '__manual_trigger__' &&
              to != '__manual_trigger__' &&
              from != '__compose_draft__' &&
              to != '__compose_draft__';
        })
        .toList();
  }

  /// First save of a draft canvas: upsert with meta + current nodes, then select.
  Future<String?> persistDraft({
    required String id,
    required String title,
    String group = 'other',
    String category = 'general',
    String? service,
  }) async {
    final g = state.graph;
    if (g == null || !state.isDraft) return null;
    final fid = id.trim().isEmpty
        ? 'AUTH_${DateTime.now().millisecondsSinceEpoch}'
        : id.trim();
    final svc = (service ?? '').trim();
    await _repo.upsertFlow({
      'id': fid,
      'title': title.trim().isEmpty ? fid : title.trim(),
      'gate': 'prod_safe',
      'group': group,
      'category': category,
      'description': '',
      'tags': ['authored'],
      'created_by': 'authored',
      'api_pack': svc.isNotEmpty ? svc : null,
      'credential_id': state.credentialId,
      'env_default': state.env,
      'variables': <String, dynamic>{},
      'nodes': _persistableNodes(g),
      'edges': _persistableEdges(g),
    });
    await load();
    await selectFlow(fid);
    return fid;
  }

  Future<String?> createFlow({
    required String id,
    required String title,
    String group = 'other',
    String category = 'general',
    String? service,
    List<Map<String, dynamic>>? nodes,
    List<Map<String, dynamic>>? edges,
  }) async {
    final fid = id.trim().isEmpty
        ? 'AUTH_${DateTime.now().millisecondsSinceEpoch}'
        : id.trim();
    final svc = (service ?? '').trim();
    await _repo.upsertFlow({
      'id': fid,
      'title': title.trim().isEmpty ? fid : title.trim(),
      'gate': 'prod_safe',
      'group': group,
      'category': category,
      'description': '',
      'tags': ['authored'],
      'created_by': 'authored',
      'api_pack': svc.isNotEmpty ? svc : null,
      'credential_id': state.credentialId,
      'env_default': state.env,
      'variables': <String, dynamic>{},
      'nodes': nodes ?? <Map<String, dynamic>>[],
      'edges': edges ?? <Map<String, dynamic>>[],
    });
    await load();
    await selectFlow(fid);
    return fid;
  }

  void updateSelectedNode(Map<String, dynamic> patch) {
    final nid = state.selectedLogNodeId;
    final g = state.graph;
    if (nid == null || g == null || nid == '__manual_trigger__') return;
    final nodes = List<Map<String, dynamic>>.from(
      (g['nodes'] is List)
          ? (g['nodes'] as List)
              .whereType<Map>()
              .map((e) => Map<String, dynamic>.from(e))
          : const [],
    );
    final idx = nodes.indexWhere((n) => '${n['id']}' == nid);
    if (idx < 0) return;
    nodes[idx] = {...nodes[idx], ...patch};
    final nextGraph = Map<String, dynamic>.from(g)..['nodes'] = nodes;
    emit(state.copyWith(graph: nextGraph, graphDirty: true));
  }

  Future<void> saveProposedFlow(Map<String, dynamic> proposal) async {
    await _repo.upsertFlow({
      'id': proposal['id'],
      'title': proposal['title'] ?? proposal['id'],
      'gate': proposal['gate'] ?? 'prod_safe',
      'group': proposal['group'] ?? 'other',
      'category': proposal['category'] ?? 'general',
      'description': proposal['description'] ?? '',
      'tags': proposal['tags'] ?? ['proposed'],
      'created_by': 'llm',
      'nodes': proposal['nodes'] ?? [],
      'credential_id': state.credentialId,
      'env_default': state.env,
    });
    await load();
  }

  Future<Map<String, dynamic>> saveSchedule({
    required String cron,
    bool enabled = true,
  }) async {
    final fid = state.selectedFlowId;
    if (fid == null) throw StateError('no flow selected');
    return _repo.upsertSchedule(
      flowId: fid,
      cron: cron,
      env: state.env,
      credentialId: state.credentialId,
      enabled: enabled,
    );
  }

  @override
  Future<void> close() {
    _poll?.cancel();
    _queryDebounce?.cancel();
    return super.close();
  }
}

