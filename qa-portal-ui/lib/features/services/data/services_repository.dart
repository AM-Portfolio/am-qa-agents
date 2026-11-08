import '../../../core/network/api_client.dart';
import '../../../core/network/json_lists.dart';
import '../../specs/data/specs_repository.dart';

class ServicesRepository {
  ServicesRepository(this._api, this._specs);

  final ApiClient _api;
  final SpecsRepository _specs;

  Future<({List<String> ids, Map<String, String> labels})> listServices() =>
      _specs.listServices();

  Future<Map<String, dynamic>> overview(
    String serviceKey, {
    String environment = 'dev',
    int runsLimit = 25,
  }) async {
    final res = await _api.get(
      '/api/services/$serviceKey/overview',
      query: {
        'environment': environment,
        'runs_limit': runsLimit,
      },
    );
    return asMap(res.data);
  }
}
