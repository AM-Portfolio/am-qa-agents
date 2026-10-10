part of 'flows_cubit.dart';

extension FlowsCubitRuntime on FlowsCubit {
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
}
