import '../../../core/network/api_client.dart';
import '../../../core/network/json_lists.dart';

class ExecuteRepository {
  ExecuteRepository(this._api);

  final ApiClient _api;

  Future<List<Map<String, dynamic>>> listConfigs() async {
    final res = await _api.get('/api/configs');
    return mapList(res.data, keys: const ['configs', 'profiles', 'items']);
  }

  Future<Map<String, dynamic>> uiCatalog() async {
    final res = await _api.get('/api/ui-test/profiles');
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> serviceApis(
    String service, {
    String? environment,
  }) async {
    final res = await _api.get(
      '/api/catalog/$service/apis',
      query: {if (environment != null) 'environment': environment},
    );
    return mapList(res.data, keys: const ['apis', 'items']);
  }

  Future<List<String>> openapiVersions(String service) async {
    final res = await _api.get('/api/catalog/$service/openapi/versions');
    final data = asMap(res.data);
    final envs = data['environments'];
    final versions = <String>{};
    if (envs is Map) {
      for (final v in envs.values) {
        if (v is Map && v['version'] != null) versions.add('${v['version']}');
        if (v is List) {
          for (final x in v) {
            if (x is Map && x['version'] != null) {
              versions.add('${x['version']}');
            } else if (x is String) {
              versions.add(x);
            }
          }
        }
      }
    }
    final list = data['versions'];
    if (list is List) {
      for (final x in list) {
        if (x is String) versions.add(x);
        if (x is Map && x['version'] != null) versions.add('${x['version']}');
      }
    }
    return versions.toList()..sort();
  }

  Future<void> stopRun(String id) async {
    await _api.post('/api/runs/$id/stop');
  }

  Future<Map<String, dynamic>> execute({
    String? configId,
    String? service,
    String? audience,
    String? environment,
    String testType = 'k6',
    int vus = 1,
    int calls = 1,
    String? profile,
    String? uiProfile,
    String? uiSuite,
    List<String>? reportFormats,
    List<String>? apiIds,
    String? openapiVersion,
    String? payloadSet,
  }) async {
    int? payloadSetVersion;
    if (payloadSet != null && payloadSet.isNotEmpty) {
      payloadSetVersion = int.tryParse(payloadSet);
    }
    final res = await _api.post(
      '/api/runs/execute',
      data: {
        if (configId != null && configId.isNotEmpty) 'config_id': configId,
        if (service != null && service.isNotEmpty) 'service': service,
        if (audience != null && audience.isNotEmpty) 'audience': audience,
        if (environment != null && environment.isNotEmpty) 'environment': environment,
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
        if (payloadSetVersion != null) 'payload_set_version': payloadSetVersion,
      },
    );
    return asMap(res.data);
  }
}
