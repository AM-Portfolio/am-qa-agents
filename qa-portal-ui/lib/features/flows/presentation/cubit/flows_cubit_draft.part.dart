part of 'flows_cubit.dart';

extension FlowsCubitDraft on FlowsCubit {
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
}
