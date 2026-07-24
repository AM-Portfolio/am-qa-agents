import '../../../core/network/api_client.dart';

class RunsRepository {
  RunsRepository(this._api);

  final ApiClient _api;

  Future<List<Map<String, dynamic>>> listRuns({
    String? status,
    int limit = 50,
  }) async {
    final res = await _api.get(
      '/api/runs',
      query: {
        if (status != null && status.isNotEmpty) 'status': status,
        'limit': limit,
      },
    );
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

  Future<Map<String, dynamic>> getRun(String id) async {
    final res = await _api.get('/api/runs/$id');
    final data = res.data;
    if (data is Map) return Map<String, dynamic>.from(data);
    return {};
  }

  Future<void> stopRun(String id) async {
    await _api.post('/api/runs/$id/stop');
  }
}
