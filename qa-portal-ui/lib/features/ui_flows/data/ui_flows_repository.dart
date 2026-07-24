import '../../../core/network/api_client.dart';

class UiFlowsRepository {
  UiFlowsRepository(this._api);

  final ApiClient _api;

  Future<Map<String, dynamic>> catalog() async {
    final res = await _api.get('/api/ui-test/profiles');
    if (res.data is Map) return Map<String, dynamic>.from(res.data as Map);
    return {};
  }

  Future<Map<String, dynamic>> createFlow(Map<String, dynamic> body) async {
    final res = await _api.post('/api/ui-test/flows', data: body);
    if (res.data is Map) return Map<String, dynamic>.from(res.data as Map);
    return {};
  }

  Future<Map<String, dynamic>> updateFlow(
    String id,
    Map<String, dynamic> body,
  ) async {
    final res = await _api.put('/api/ui-test/flows/$id', data: body);
    if (res.data is Map) return Map<String, dynamic>.from(res.data as Map);
    return {};
  }

  Future<void> deleteFlow(String id, {bool reset = false}) async {
    await _api.delete('/api/ui-test/flows/$id', query: {if (reset) 'reset': 1});
  }

  Future<Map<String, dynamic>> createSuite(Map<String, dynamic> body) async {
    final res = await _api.post('/api/ui-test/suites', data: body);
    if (res.data is Map) return Map<String, dynamic>.from(res.data as Map);
    return {};
  }

  Future<Map<String, dynamic>> updateSuite(
    String id,
    Map<String, dynamic> body,
  ) async {
    final res = await _api.put('/api/ui-test/suites/$id', data: body);
    if (res.data is Map) return Map<String, dynamic>.from(res.data as Map);
    return {};
  }

  Future<void> deleteSuite(String id, {bool reset = false}) async {
    await _api.delete('/api/ui-test/suites/$id', query: {if (reset) 'reset': 1});
  }
}
