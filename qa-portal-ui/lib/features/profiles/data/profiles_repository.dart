import '../../../core/network/api_client.dart';

class ProfilesRepository {
  ProfilesRepository(this._api);

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
}
