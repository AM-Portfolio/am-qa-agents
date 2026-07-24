import '../../../core/network/api_client.dart';

class ExecuteRepository {
  ExecuteRepository(this._api);

  final ApiClient _api;

  Future<List<Map<String, dynamic>>> listConfigs() async {
    final res = await _api.get('/api/configs');
    final data = res.data;
    if (data is Map && data['items'] is List) {
      return (data['items'] as List)
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
    }
    if (data is List) {
      return data
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> execute({
    required String configId,
    String testType = 'k6',
    int vus = 1,
    int calls = 1,
  }) async {
    final res = await _api.post(
      '/api/runs/execute',
      data: {
        'config_id': configId,
        'test_type': testType,
        'vus': vus,
        'calls_per_vu': calls,
      },
    );
    final data = res.data;
    if (data is Map) return Map<String, dynamic>.from(data);
    return {};
  }
}
