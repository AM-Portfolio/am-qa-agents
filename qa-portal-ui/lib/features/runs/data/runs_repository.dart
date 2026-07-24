import '../../../core/network/api_client.dart';
import '../../../core/network/json_lists.dart';

class RunsListResult {
  const RunsListResult({required this.runs, required this.total});

  final List<Map<String, dynamic>> runs;
  final int total;
}

class RunsRepository {
  RunsRepository(this._api);

  final ApiClient _api;

  Future<RunsListResult> listRuns({
    String? status,
    String? service,
    String? environment,
    String? configName,
    String? q,
    String? testType,
    String? from,
    String? to,
    int limit = 50,
    int offset = 0,
  }) async {
    final res = await _api.get(
      '/api/runs',
      query: {
        if (status != null && status.isNotEmpty) 'status': status,
        if (service != null && service.isNotEmpty) 'service': service,
        if (environment != null && environment.isNotEmpty) 'environment': environment,
        if (configName != null && configName.isNotEmpty) 'config_name': configName,
        if (q != null && q.isNotEmpty) 'q': q,
        if (testType != null && testType.isNotEmpty) 'test_type': testType,
        if (from != null && from.isNotEmpty) 'from': from,
        if (to != null && to.isNotEmpty) 'to': to,
        'limit': limit,
        'offset': offset,
      },
    );
    final runs = mapList(res.data, keys: const ['runs', 'items']);
    return RunsListResult(runs: runs, total: asTotal(res.data, fallback: runs.length));
  }

  Future<Map<String, dynamic>> getRun(String id) async {
    final res = await _api.get('/api/runs/$id');
    return asMap(res.data);
  }

  Future<void> stopRun(String id) async {
    await _api.post('/api/runs/$id/stop');
  }

  Future<Map<String, dynamic>> exportRun(String id) async {
    final res = await _api.get('/api/runs/$id/export');
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> saveAsConfig(String id, {String? name}) async {
    final res = await _api.post(
      '/api/runs/$id/save-config',
      query: {if (name != null && name.isNotEmpty) 'name': name},
    );
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> execute({
    required String configId,
    String testType = 'k6',
    int vus = 1,
    int calls = 1,
    String? profile,
    String? uiProfile,
    String? uiSuite,
    List<String>? reportFormats,
    List<String>? apiIds,
    String? openapiVersion,
  }) async {
    final res = await _api.post(
      '/api/runs/execute',
      data: {
        'config_id': configId,
        'test_type': testType,
        'vus': vus,
        'iterations': calls,
        if (profile != null) 'profile': profile,
        if (uiProfile != null && uiProfile.isNotEmpty) 'ui_profile': uiProfile,
        if (uiSuite != null && uiSuite.isNotEmpty) 'ui_suite': uiSuite,
        if (reportFormats != null) 'report_formats': reportFormats,
        if (apiIds != null && apiIds.isNotEmpty) 'api_ids': apiIds,
        if (openapiVersion != null && openapiVersion.isNotEmpty)
          'openapi_version': openapiVersion,
      },
    );
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> artifacts(String id) async {
    final res = await _api.get('/api/runs/$id/artifacts');
    return mapList(res.data, keys: const ['artifacts', 'items']);
  }

  Future<Map<String, dynamic>> baseline(String id) async {
    final res = await _api.get('/api/runs/$id/baseline');
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> runApis(
    String id, {
    bool failedOnly = false,
    String? q,
  }) async {
    final res = await _api.get(
      '/api/runs/$id/apis',
      query: {
        if (failedOnly) 'failed_only': true,
        if (q != null && q.isNotEmpty) 'q': q,
      },
    );
    return mapList(res.data, keys: const ['apis', 'items']);
  }

  Future<List<Map<String, dynamic>>> traces(
    String id, {
    String? apiId,
    bool failedOnly = false,
    int limit = 100,
  }) async {
    final res = await _api.get(
      '/api/runs/$id/traces',
      query: {
        if (apiId != null && apiId.isNotEmpty) 'api_id': apiId,
        if (failedOnly) 'failed_only': true,
        'limit': limit,
      },
    );
    return mapList(res.data, keys: const ['traces', 'items']);
  }

  Future<Map<String, dynamic>> traceAt(String id, int index) async {
    final res = await _api.get('/api/runs/$id/traces/$index');
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> apiTrace(String id, String apiId) async {
    final res = await _api.get('/api/runs/$id/apis/$apiId/trace');
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> savePayload(
    String runId,
    String apiId, {
    String? name,
  }) async {
    final res = await _api.post(
      '/api/runs/$runId/apis/$apiId/save-payload',
      data: {if (name != null) 'name': name},
    );
    return asMap(res.data);
  }
}
