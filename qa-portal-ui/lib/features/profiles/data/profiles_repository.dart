import '../../../core/network/api_client.dart';
import '../../../core/network/json_lists.dart';

class ProfilesRepository {
  ProfilesRepository(this._api);

  final ApiClient _api;

  Future<List<Map<String, dynamic>>> listConfigs() async {
    final res = await _api.get('/api/configs');
    return mapList(res.data, keys: const ['configs', 'profiles', 'items']);
  }

  Future<Map<String, dynamic>> getConfig(String id) async {
    final res = await _api.get('/api/configs/$id');
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> createConfig(Map<String, dynamic> body) async {
    final res = await _api.post('/api/configs', data: body);
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> updateConfig(
    String id,
    Map<String, dynamic> body,
  ) async {
    final res = await _api.put('/api/configs/$id', data: body);
    return asMap(res.data);
  }

  Future<void> deleteConfig(String id) async {
    await _api.delete('/api/configs/$id');
  }
}
