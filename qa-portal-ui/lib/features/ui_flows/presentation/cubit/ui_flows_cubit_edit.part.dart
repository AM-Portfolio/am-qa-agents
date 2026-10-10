part of 'ui_flows_cubit.dart';

extension UiFlowsCubitEdit on UiFlowsCubit {
  Future<void> load({String? keepSelected}) async {
    emit(state.copyWith(loading: true, clearError: true));
    try {
      final cat = await _repo.catalog();
      final flows = <Map<String, dynamic>>[];
      final seen = <String>{};

      void addMap(Map raw) {
        final m = Map<String, dynamic>.from(raw);
        final id = '${m['id'] ?? ''}'.trim();
        if (id.isEmpty) return;
        if (!seen.add(id)) {
          final idx = flows.indexWhere((f) => '${f['id']}' == id);
          if (idx >= 0 && m.keys.length >= flows[idx].keys.length) {
            flows[idx] = m;
          }
          return;
        }
        flows.add(m);
      }

      void addStub(String id) {
        final trimmed = id.trim();
        if (trimmed.isEmpty || seen.contains(trimmed)) return;
        seen.add(trimmed);
        flows.add({'id': trimmed, 'label': trimmed});
      }

      for (final key in ['flows', 'custom_flows']) {
        final list = cat[key];
        if (list is! List) continue;
        for (final e in list) {
          if (e is Map) addMap(e);
        }
      }
      for (final key in ['deterministic', 'release_gate']) {
        final list = cat[key];
        if (list is! List) continue;
        for (final e in list) {
          if (e is Map) {
            addMap(e);
          } else if (e is String) {
            addStub(e);
          }
        }
      }

      final suites = <Map<String, dynamic>>[];
      final suiteSeen = <String>{};
      final rawSuites = cat['suites'];
      if (rawSuites is List) {
        for (final e in rawSuites) {
          if (e is Map) {
            final m = Map<String, dynamic>.from(e);
            final id = '${m['id'] ?? ''}'.trim();
            if (id.isEmpty || !suiteSeen.add(id)) continue;
            suites.add(m);
          } else if (e is String) {
            final id = e.trim();
            if (id.isEmpty || !suiteSeen.add(id)) continue;
            suites.add({'id': id, 'label': id});
          }
        }
      }
      final agent = cat['agent'];
      final agentMap = agent is Map ? Map<String, dynamic>.from(agent) : null;
      final online = agentMap?['online'] == true || cat['agent_online'] == true;
      final url = agentMap?['url']?.toString() ?? cat['agent_url']?.toString();
      final err = agentMap?['error']?.toString() ?? cat['error']?.toString();

      final prefer = keepSelected ?? state.selectedFlowId;
      final selected = (prefer != null && flows.any((f) => '${f['id']}' == prefer))
          ? prefer
          : (flows.isNotEmpty ? '${flows.first['id']}' : null);

      emit(
        state.copyWith(
          loading: false,
          flows: flows,
          suites: suites,
          agentOnline: online,
          agentUrl: url,
          error: err,
          selectedFlowId: selected,
        ),
      );
      if (selected != null) {
        _loadGraphFor(selected, flows);
      }
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }

  void selectFlow(String id) {
    if (id == state.selectedFlowId) return;
    _poll?.cancel();
    emit(
      state.copyWith(
        selectedFlowId: id,
        graphDirty: false,
        clearSelectedNode: true,
        clearRun: true,
        running: false,
      ),
    );
    _loadGraphFor(id, state.flows);
  }

  void setBottomTab(int tab) => emit(state.copyWith(bottomTab: tab));

  void _loadGraphFor(String id, List<Map<String, dynamic>> flows) {
    Map<String, dynamic>? flow;
    for (final f in flows) {
      if ('${f['id']}' == id) {
        flow = f;
        break;
      }
    }
    if (flow == null) {
      emit(state.copyWith(clearGraph: true));
      return;
    }
    final steps = <String>[
      for (final s in (flow['steps'] is List ? flow['steps'] as List : const []))
        '$s'.trim(),
    ].where((s) => s.isNotEmpty).toList();
    final verifs = <String>[
      for (final s
          in (flow['verifications'] is List ? flow['verifications'] as List : const []))
        '$s'.trim(),
    ].where((s) => s.isNotEmpty).toList();
    final existing = flow['graph'] is Map
        ? Map<String, dynamic>.from(flow['graph'] as Map)
        : null;
    final graph = graphFromStepLists(
      flowId: id,
      steps: steps,
      verifications: verifs,
      existingGraph: existing,
    );
    emit(state.copyWith(graph: graph, graphDirty: false));
  }

  void selectNode(String id) {
    emit(state.copyWith(selectedNodeId: id));
  }

  void addStepAfter(String afterId) {
    final g = state.graph;
    if (g == null) return;
    final nodes = [
      for (final n in (g['nodes'] is List ? g['nodes'] as List : const []))
        if (n is Map) Map<String, dynamic>.from(n),
    ];
    final edges = [
      for (final e in (g['edges'] is List ? g['edges'] as List : const []))
        if (e is Map) Map<String, dynamic>.from(e),
    ];
    final idx = nodes.indexWhere((n) => '${n['id']}' == afterId);
    if (idx < 0) return;
    final newId = 'step_${DateTime.now().millisecondsSinceEpoch}';
    final baseX = (nodes[idx]['x'] is num)
        ? (nodes[idx]['x'] as num).toDouble()
        : defaultNodeX(idx);
    final baseY = (nodes[idx]['y'] is num)
        ? (nodes[idx]['y'] as num).toDouble()
        : defaultNodeY(idx);
    final newNode = {
      'id': newId,
      'kind': 'ui_step',
      'label': 'New step',
      'method': 'STEP',
      'x': baseX + 280,
      'y': baseY,
    };
    // Rewire: afterId -> newId -> previous targets of afterId
    final outgoing = edges.where((e) => '${e['from']}' == afterId).toList();
    edges.removeWhere((e) => '${e['from']}' == afterId);
    edges.add({
      'id': '$afterId->$newId',
      'from': afterId,
      'to': newId,
      'trigger': afterId == kManualTriggerId,
    });
    for (final e in outgoing) {
      edges.add({
        'id': '$newId->${e['to']}',
        'from': newId,
        'to': '${e['to']}',
      });
    }
    nodes.insert(idx + 1, newNode);
    emit(
      state.copyWith(
        graph: {...g, 'nodes': nodes, 'edges': edges},
        graphDirty: true,
        selectedNodeId: newId,
      ),
    );
  }

  void deleteNode(String nodeId) {
    if (nodeId == kManualTriggerId) return;
    final g = state.graph;
    if (g == null) return;
    final nodes = [
      for (final n in (g['nodes'] is List ? g['nodes'] as List : const []))
        if (n is Map && '${n['id']}' != nodeId) Map<String, dynamic>.from(n),
    ];
    final edgesIn = [
      for (final e in (g['edges'] is List ? g['edges'] as List : const []))
        if (e is Map) Map<String, dynamic>.from(e),
    ];
    final preds = [
      for (final e in edgesIn)
        if ('${e['to']}' == nodeId) '${e['from']}',
    ];
    final succs = [
      for (final e in edgesIn)
        if ('${e['from']}' == nodeId) '${e['to']}',
    ];
    final edges = [
      for (final e in edgesIn)
        if ('${e['from']}' != nodeId && '${e['to']}' != nodeId) e,
    ];
    for (final p in preds) {
      for (final s in succs) {
        edges.add({
          'id': '$p->$s',
          'from': p,
          'to': s,
          'trigger': p == kManualTriggerId,
        });
      }
    }
    emit(
      state.copyWith(
        graph: {...g, 'nodes': nodes, 'edges': edges},
        graphDirty: true,
        clearSelectedNode: state.selectedNodeId == nodeId,
      ),
    );
  }

  void renameSelectedNode(String label) {
    final nid = state.selectedNodeId;
    final g = state.graph;
    if (nid == null || g == null || nid == kManualTriggerId) return;
    final fixed = <Map<String, dynamic>>[];
    for (final n in (g['nodes'] is List ? g['nodes'] as List : const [])) {
      if (n is! Map) continue;
      final m = Map<String, dynamic>.from(n);
      if ('${m['id']}' == nid) m['label'] = label.trim();
      fixed.add(m);
    }
    emit(
      state.copyWith(
        graph: {...g, 'nodes': fixed},
        graphDirty: true,
      ),
    );
  }

  Future<void> saveGraph() async {
    final id = state.selectedFlowId;
    final g = state.graph;
    final flow = state.selectedFlow;
    if (id == null || g == null || flow == null) return;
    emit(state.copyWith(saving: true, clearError: true));
    try {
      final lists = listsFromGraph(g);
      final body = <String, dynamic>{
        'id': id,
        'label': flow['label'] ?? id,
        'group': flow['group'] ?? 'Custom',
        'summary': flow['summary'] ?? '',
        'graph': g,
        'steps': lists.steps,
        'verifications': lists.verifications,
      };
      final runsAs = '${flow['runs_as'] ?? id}'.trim();
      if (flow['custom'] == true || runsAs != id) {
        body['runs_as'] = runsAs.isEmpty ? id : runsAs;
      }
      final exists = state.flows.any((f) => '${f['id']}' == id);
      if (exists) {
        await _repo.updateFlow(id, body);
      } else {
        await _repo.createFlow(body);
      }
      await load(keepSelected: id);
      emit(state.copyWith(saving: false, graphDirty: false));
    } catch (e) {
      emit(state.copyWith(saving: false, error: e.toString()));
    }
  }

  Future<void> saveFlow(Map<String, dynamic> body) async {
    final id = body['id']?.toString().trim() ?? '';
    if (id.isEmpty) throw ArgumentError('Flow id required');
    if (!_flowIdPattern.hasMatch(id)) {
      throw ArgumentError('Flow id must match [A-Z0-9_]+');
    }
    final exists = state.flows.any((f) => '${f['id']}' == id);
    if (exists) {
      await _repo.updateFlow(id, body);
    } else {
      await _repo.createFlow(body);
    }
    await load(keepSelected: id);
  }

  Future<void> saveSuite(Map<String, dynamic> body) async {
    final id = body['id']?.toString().trim() ?? '';
    if (id.isEmpty) throw ArgumentError('Suite id required');
    if (!_flowIdPattern.hasMatch(id)) {
      throw ArgumentError('Suite id must match [A-Z0-9_]+');
    }
    final profiles = body['profiles'];
    if (profiles is! List || profiles.isEmpty) {
      throw ArgumentError('Suite profiles must be a non-empty list');
    }
    final exists = state.suites.any((s) => '${s['id']}' == id);
    if (exists) {
      await _repo.updateSuite(id, body);
    } else {
      await _repo.createSuite(body);
    }
    await load(keepSelected: state.selectedFlowId);
  }

  Future<void> deleteFlow(String id, {bool reset = false}) async {
    await _repo.deleteFlow(id, reset: reset);
    await load();
  }

  Future<void> deleteSuite(String id, {bool reset = false}) async {
    await _repo.deleteSuite(id, reset: reset);
    await load(keepSelected: state.selectedFlowId);
  }
}
