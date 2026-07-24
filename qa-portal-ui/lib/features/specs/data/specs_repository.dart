import '../../../core/network/api_client.dart';
import '../../../core/network/json_lists.dart';

class SpecsRepository {
  SpecsRepository(this._api);

  final ApiClient _api;

  Future<Map<String, dynamic>> catalog() async {
    final res = await _api.get('/api/catalog');
    return asMap(res.data);
  }

  /// Catalog services only (`GET /api/catalog`) — no registrations merge.
  Future<({List<String> ids, Map<String, String> labels})> listServices() async {
    final cat = await catalog();
    final labels = <String, String>{};
    final ids = <String>{};

    void addService(dynamic raw) {
      if (raw is String) {
        final id = raw.trim();
        if (id.isEmpty) return;
        ids.add(id);
        labels.putIfAbsent(id, () => id);
        return;
      }
      if (raw is! Map) return;
      final m = Map<String, dynamic>.from(raw);
      final id = '${m['id'] ?? m['service'] ?? m['name'] ?? m['label'] ?? ''}'.trim();
      if (id.isEmpty) return;
      ids.add(id);
      final label = '${m['label'] ?? m['name'] ?? m['service'] ?? id}'.trim();
      labels[id] = label.isEmpty ? id : label;
    }

    final servicesField = cat['services'];
    if (servicesField is List) {
      for (final s in servicesField) {
        addService(s);
      }
    } else if (servicesField is Map) {
      for (final e in servicesField.entries) {
        final key = '${e.key}';
        ids.add(key);
        if (e.value is Map) {
          addService({...Map<String, dynamic>.from(e.value as Map), 'id': key});
        } else {
          labels.putIfAbsent(key, () => key);
        }
      }
    }

    final list = ids.toList()..sort();
    return (ids: list, labels: labels);
  }

  Future<Map<String, dynamic>> openapi(
    String service, {
    String? environment,
    bool effective = true,
  }) async {
    final res = await _api.get(
      '/api/catalog/$service/openapi',
      query: {
        if (environment != null) 'environment': environment,
        if (effective) 'effective': 1,
      },
    );
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> apis(
    String service, {
    String? environment,
  }) async {
    final res = await _api.get(
      '/api/catalog/$service/apis',
      query: {if (environment != null) 'environment': environment},
    );
    return mapList(res.data, keys: const ['apis', 'items']);
  }

  Future<String?> tryToken() async {
    final res = await _api.get('/api/platform/try-token');
    final data = asMap(res.data);
    return data['access_token']?.toString() ??
        data['token']?.toString() ??
        data['jwt']?.toString();
  }

  Future<Map<String, dynamic>> platformHealth() async {
    final res = await _api.get('/api/platform/health');
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> payloadSets(String service) async {
    final res = await _api.get('/api/payload-sets/$service');
    return mapList(res.data, keys: const ['sets', 'payload_sets', 'items', 'versions']);
  }

  Future<Map<String, dynamic>> getPayloadSet(String service, String version) async {
    final res = await _api.get('/api/payload-sets/$service/$version');
    return asMap(res.data);
  }

  Future<List<Map<String, dynamic>>> listPayloads({
    required String service,
    String? apiId,
  }) async {
    final res = await _api.get(
      '/api/payloads',
      query: {
        'service': service,
        if (apiId != null && apiId.isNotEmpty) 'api_id': apiId,
      },
    );
    return mapList(res.data, keys: const ['payloads', 'items']);
  }

  Future<Map<String, dynamic>> savePayload({
    required String service,
    required String apiId,
    required Map<String, dynamic> request,
    String name = 'working',
    int? setVersion,
    bool intoSet = true,
    bool bumpSet = false,
    Map<String, dynamic>? response,
    Map<String, dynamic>? meta,
  }) async {
    final res = await _api.post(
      '/api/payloads',
      data: {
        'service': service,
        'api_id': apiId,
        'name': name,
        'request': request,
        if (response != null) 'response': response,
        if (meta != null) 'meta': meta,
        'into_set': intoSet,
        'bump_set': bumpSet,
        if (setVersion != null) 'set_version': setVersion,
      },
    );
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> ensurePayloadSet(String service) async {
    final res = await _api.post('/api/payload-sets/$service/ensure');
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> activatePayloadSet(
    String service,
    String version,
  ) async {
    final res = await _api.post('/api/payload-sets/$service/$version/activate');
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> buildPayload({
    required String service,
    required String environment,
    required String method,
    required String path,
  }) async {
    final res = await _api.post(
      '/api/payloads/build',
      data: {
        'service': service,
        'environment': environment,
        'method': method,
        'path': path,
      },
    );
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> ensureWorking({
    required String service,
    required String environment,
    required String method,
    required String path,
  }) async {
    final res = await _api.post(
      '/api/payloads/ensure-working',
      data: {
        'service': service,
        'environment': environment,
        'method': method,
        'path': path,
      },
    );
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> prepareMcp({
    required String service,
    required String environment,
  }) async {
    final res = await _api.post(
      '/api/payloads/prepare-mcp',
      data: {
        'service': service,
        'environment': environment,
        'write_overlays': true,
        'try_each': false,
      },
    );
    return asMap(res.data);
  }
}
