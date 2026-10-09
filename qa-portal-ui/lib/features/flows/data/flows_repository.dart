import '../../../core/network/api_client.dart';
import '../../../core/network/json_lists.dart';

class FlowsRepository {
  FlowsRepository(this._api);

  final ApiClient _api;

  Future<Map<String, dynamic>> listFlowsPage({
    String? group,
    String? category,
    String? q,
    String? apiPack,
    String? service,
    int limit = 100,
    int offset = 0,
    bool facets = false,
  }) async {
    final res = await _api.get(
      '/api/flows',
      query: {
        if (group != null && group.isNotEmpty) 'group': group,
        if (category != null && category.isNotEmpty) 'category': category,
        if (q != null && q.isNotEmpty) 'q': q,
        if (apiPack != null && apiPack.isNotEmpty) 'api_pack': apiPack,
        if (service != null && service.isNotEmpty) 'service': service,
        'limit': '$limit',
        'offset': '$offset',
        if (facets) 'facets': 'true',
      },
    );
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> listFlows({
    String? group,
    String? category,
    String? q,
    String? apiPack,
    String? service,
    int limit = 100,
    int offset = 0,
  }) async {
    final data = await listFlowsPage(
      group: group,
      category: category,
      q: q,
      apiPack: apiPack,
      service: service,
      limit: limit,
      offset: offset,
    );
    return mapList(data, keys: const ['flows']);
  }

  Future<List<String>> listCatalogServices() async {
    final res = await _api.get('/api/catalog');
    final data = asMap(res.data);
    final ids = <String>{};
    final services = data['services'];
    if (services is List) {
      for (final raw in services) {
        if (raw is String && raw.trim().isNotEmpty) {
          ids.add(raw.trim());
        } else if (raw is Map) {
          final id =
              '${raw['id'] ?? raw['service'] ?? raw['name'] ?? ''}'.trim();
          if (id.isNotEmpty) ids.add(id);
        }
      }
    }
    final sorted = ids.toList()..sort();
    return sorted;
  }

  Future<Map<String, dynamic>?> getPayloadSet(
    String service, {
    int? version,
  }) async {
    final path = version == null
        ? '/api/payload-sets/${Uri.encodeComponent(service)}'
        : '/api/payload-sets/${Uri.encodeComponent(service)}/$version';
    final res = await _api.get(path);
    final data = asMap(res.data);
    if (data.isEmpty) return null;
    // list endpoint returns {sets, active_version}; detail returns apis
    if (data['apis'] is Map) return data;
    final active = data['active_version'];
    final ver = version ??
        (active is int
            ? active
            : int.tryParse('$active') ??
                ((data['sets'] is List && (data['sets'] as List).isNotEmpty)
                    ? int.tryParse('${(data['sets'] as List).first['version']}')
                    : null));
    if (ver == null) return data;
    final detail = await _api.get(
      '/api/payload-sets/${Uri.encodeComponent(service)}/$ver',
    );
    return asMap(detail.data);
  }

  Future<Map<String, dynamic>> proposeScenarios({
    required String service,
    String? group,
    String? category,
    String env = 'prod',
    int maxScenarios = 5,
    bool useLlm = true,
  }) async {
    final res = await _api.post(
      '/api/flows/propose',
      data: {
        'service': service,
        if (group != null) 'group': group,
        if (category != null) 'category': category,
        'env': env,
        'max_scenarios': maxScenarios,
        'use_llm': useLlm,
      },
    );
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> listSchedules({String? flowId}) async {
    final res = await _api.get(
      '/api/flows/schedules',
      query: {if (flowId != null && flowId.isNotEmpty) 'flow_id': flowId},
    );
    final data = asMap(res.data);
    return mapList(data, keys: const ['schedules']);
  }

  Future<Map<String, dynamic>> upsertSchedule({
    required String flowId,
    required String cron,
    String env = 'prod',
    String? credentialId,
    bool enabled = true,
  }) async {
    final res = await _api.post(
      '/api/flows/schedules',
      data: {
        'flow_id': flowId,
        'cron': cron,
        'env': env,
        if (credentialId != null && credentialId.isNotEmpty)
          'credential_id': credentialId,
        'enabled': enabled,
      },
    );
    return asMap(res.data);
  }

  Future<void> disableSchedule(String scheduleId) async {
    await _api.post('/api/flows/schedules/$scheduleId/disable');
  }

  Future<Map<String, dynamic>> upsertFlow(Map<String, dynamic> body) async {
    final res = await _api.post('/api/flows', data: body);
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> updateFlow(
    String flowId,
    Map<String, dynamic> body,
  ) async {
    final res = await _api.put(
      '/api/flows/${Uri.encodeComponent(flowId)}',
      data: body,
    );
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> getFlow(String flowId) async {
    final res = await _api.get('/api/flows/${Uri.encodeComponent(flowId)}');
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> quickTestNode(
    String flowId,
    String nodeId, {
    String env = 'prod',
    String? credentialId,
    Map<String, dynamic>? variables,
  }) async {
    final res = await _api.post(
      '/api/flows/${Uri.encodeComponent(flowId)}/nodes/${Uri.encodeComponent(nodeId)}/quick-test',
      data: {
        'env': env,
        if (credentialId != null && credentialId.isNotEmpty)
          'credential_id': credentialId,
        if (variables != null) 'variables': variables,
      },
    );
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> listOpenApiTools(
    String service, {
    String? environment,
  }) async {
    final res = await _api.get(
      '/api/catalog/${Uri.encodeComponent(service)}/openapi/tools',
      query: {
        if (environment != null && environment.isNotEmpty)
          'environment': environment,
      },
    );
    final data = asMap(res.data);
    return mapList(data, keys: const ['tools']);
  }

  Future<Map<String, dynamic>> getGraph(String flowId) async {
    final res =
        await _api.get('/api/flows/${Uri.encodeComponent(flowId)}/graph');
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> execute(
    String flowId, {
    String env = 'prod',
    String? credentialId,
    Map<String, dynamic>? variables,
    int? payloadSetVersion,
  }) async {
    final res = await _api.post(
      '/api/flows/${Uri.encodeComponent(flowId)}/execute',
      data: {
        'env': env,
        if (credentialId != null && credentialId.isNotEmpty)
          'credential_id': credentialId,
        if (variables != null) 'variables': variables,
        if (payloadSetVersion != null) 'payload_set_version': payloadSetVersion,
      },
    );
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> getRuntime(String flowId) async {
    final res = await _api.get(
      '/api/flows/${Uri.encodeComponent(flowId)}/runtime',
    );
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> setVariables(
    String flowId, {
    required Map<String, dynamic> variables,
    int? payloadSetVersion,
    bool clearPayloadPin = false,
  }) async {
    final res = await _api.put(
      '/api/flows/${Uri.encodeComponent(flowId)}/variables',
      data: {
        'variables': variables,
        if (payloadSetVersion != null) 'payload_set_version': payloadSetVersion,
        'clear_payload_pin': clearPayloadPin,
      },
    );
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> setPayloadVersion(
    String flowId, {
    required int version,
    bool activate = true,
    bool pinOnFlow = true,
    String? service,
  }) async {
    final res = await _api.put(
      '/api/flows/${Uri.encodeComponent(flowId)}/payload-version',
      data: {
        'version': version,
        'activate': activate,
        'pin_on_flow': pinOnFlow,
        if (service != null && service.isNotEmpty) 'service': service,
      },
    );
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> suitePreview({
    String? group,
    String? apiPack,
    String? category,
  }) async {
    final res = await _api.post(
      '/api/flows/suite/preview',
      data: {
        if (group != null && group.isNotEmpty) 'group': group,
        if (apiPack != null && apiPack.isNotEmpty) 'api_pack': apiPack,
        if (category != null && category.isNotEmpty) 'category': category,
      },
    );
    final data = asMap(res.data);
    return mapList(data, keys: const ['flows']);
  }

  Future<Map<String, dynamic>> suiteExecute({
    required List<String> flowIds,
    String env = 'prod',
    String? credentialId,
    int? payloadSetVersion,
    Map<String, dynamic>? variables,
  }) async {
    final res = await _api.post(
      '/api/flows/suite/execute',
      data: {
        'flow_ids': flowIds,
        'env': env,
        if (credentialId != null && credentialId.isNotEmpty)
          'credential_id': credentialId,
        if (payloadSetVersion != null) 'payload_set_version': payloadSetVersion,
        if (variables != null) 'variables': variables,
      },
    );
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> listExecutions({
    String? flowId,
    String? env,
    String? status,
    String? suiteRunId,
    int limit = 50,
  }) async {
    final res = await _api.get(
      '/api/flows/executions',
      query: {
        if (flowId != null && flowId.isNotEmpty) 'flow_id': flowId,
        if (env != null && env.isNotEmpty) 'env': env,
        if (status != null && status.isNotEmpty) 'status': status,
        if (suiteRunId != null && suiteRunId.isNotEmpty)
          'suite_run_id': suiteRunId,
        'limit': limit,
      },
    );
    final data = asMap(res.data);
    return mapList(data, keys: const ['executions']);
  }

  Future<Map<String, dynamic>> getExecution(String executionId) async {
    final res = await _api.get('/api/flows/executions/$executionId');
    return asMap(res.data);
  }

  Future<void> stopExecution(String executionId) async {
    await _api.post('/api/flows/executions/$executionId/stop');
  }

  Future<Map<String, dynamic>> executionObsLogs(
    String executionId, {
    int limit = 100,
  }) async {
    final res = await _api.get(
      '/api/flows/executions/$executionId/obs-logs',
      query: {'limit': limit},
    );
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> listCredentials({String? env}) async {
    final res = await _api.get(
      '/api/credentials',
      query: {if (env != null && env.isNotEmpty) 'env': env},
    );
    final data = asMap(res.data);
    return mapList(data, keys: const ['credentials']);
  }

  Future<List<Map<String, dynamic>>> listCredentialApps() async {
    final res = await _api.get('/api/credentials/apps');
    final data = asMap(res.data);
    return mapList(data, keys: const ['apps']);
  }

  Future<Map<String, dynamic>> upsertCredential(
    Map<String, dynamic> body, {
    String? id,
  }) async {
    if (id != null && id.isNotEmpty) {
      final res = await _api.put('/api/credentials/$id', data: body);
      return asMap(res.data);
    }
    final res = await _api.post('/api/credentials', data: body);
    return asMap(res.data);
  }

  Future<void> deleteCredential(String id) async {
    await _api.delete('/api/credentials/$id');
  }

  Future<Map<String, dynamic>> probeCredential(String id) async {
    final res = await _api.post('/api/credentials/$id/probe');
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> probeAllCredentials({String? env}) async {
    final res = await _api.post(
      '/api/credentials/probe-all',
      query: {if (env != null && env.isNotEmpty) 'env': env},
    );
    return asMap(res.data);
  }
}
