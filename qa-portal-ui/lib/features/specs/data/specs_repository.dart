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

  /// OpenAPI MCP tools for Specs (same document as Swagger / APIs).
  Future<Map<String, dynamic>> openapiTools(
    String service, {
    String? environment,
  }) async {
    final res = await _api.get(
      '/api/catalog/$service/openapi/tools',
      query: {if (environment != null) 'environment': environment},
    );
    return asMap(res.data);
  }

  /// Execute one OpenAPI tool (registry.call_tool).
  Future<Map<String, dynamic>> callOpenapiTool({
    required String service,
    required String name,
    String? environment,
    int? payloadSetVersion,
    Map<String, dynamic>? arguments,
    bool withIdentityAuth = true,
    bool recordRun = true,
  }) async {
    final res = await _api.post(
      '/api/catalog/$service/openapi/tools/call',
      data: {
        'name': name,
        if (environment != null) 'environment': environment,
        if (payloadSetVersion != null) 'payload_set_version': payloadSetVersion,
        if (arguments != null) 'arguments': arguments,
        'with_identity_auth': withIdentityAuth,
        'record_run': recordRun,
      },
      receiveTimeout: const Duration(minutes: 2),
    );
    return asMap(res.data);
  }

  /// Run selected or all OpenAPI tools sequentially; returns batch report.
  Future<Map<String, dynamic>> runOpenapiTools({
    required String service,
    String? environment,
    int? payloadSetVersion,
    List<String>? toolNames,
    bool all = false,
    Map<String, Map<String, dynamic>>? argumentsByTool,
    int? maxTools,
    bool withIdentityAuth = true,
  }) async {
    final res = await _api.post(
      '/api/catalog/$service/openapi/tools/run',
      data: {
        if (environment != null) 'environment': environment,
        if (payloadSetVersion != null) 'payload_set_version': payloadSetVersion,
        if (toolNames != null) 'tool_names': toolNames,
        'all': all,
        if (argumentsByTool != null) 'arguments_by_tool': argumentsByTool,
        if (maxTools != null) 'max_tools': maxTools,
        'with_identity_auth': withIdentityAuth,
        'record_run': false,
      },
      receiveTimeout: const Duration(minutes: 15),
    );
    return asMap(res.data);
  }

  Future<String?> tryToken({String? environment}) async {
    final res = await _api.get(
      '/api/platform/try-token',
      query: {
        if (environment != null && environment.isNotEmpty) 'environment': environment,
      },
    );
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

  Future<Map<String, dynamic>> upsertPayloadSetApi({
    required String service,
    required String apiId,
    int? version,
    required Map<String, dynamic> request,
    Map<String, dynamic>? response,
    Map<String, dynamic>? meta,
    String name = 'working',
    bool bumpSet = false,
  }) async {
    final res = await _api.put(
      '/api/payload-sets/$service/apis/$apiId',
      data: {
        'service': service,
        'api_id': apiId,
        if (version != null) 'version': version,
        'name': name,
        'request': request,
        if (response != null) 'response': response,
        if (meta != null) 'meta': meta,
        'bump_set': bumpSet,
      },
    );
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> deletePayloadSetApis({
    required String service,
    required String version,
    required List<String> apiIds,
  }) async {
    final res = await _api.delete(
      '/api/payload-sets/$service/$version/apis',
      data: {'api_ids': apiIds},
    );
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> deletePayloadSet({
    required String service,
    required String version,
  }) async {
    final res = await _api.delete('/api/payload-sets/$service/$version');
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

  Future<Map<String, dynamic>> overview(
    String serviceKey, {
    String environment = 'dev',
    int runsLimit = 25,
    bool liveOpenapi = true,
  }) async {
    final res = await _api.get(
      '/api/services/$serviceKey/overview',
      query: {
        'environment': environment,
        'runs_limit': runsLimit,
        'live_openapi': liveOpenapi,
      },
    );
    return asMap(res.data);
  }

  /// Start Temporal (or inline) Specs onboard prep for a service.
  Future<Map<String, dynamic>> startOnboard({
    required String service,
    required String environment,
    bool allowLlm = true,
    bool wait = false,
    bool useTemporal = true,
  }) async {
    final res = await _api.post(
      '/api/services/$service/onboard',
      data: {
        'environment': environment,
        'allow_llm': allowLlm,
        'wait': wait,
        'use_temporal': useTemporal,
      },
      receiveTimeout: wait
          ? const Duration(minutes: 20)
          : const Duration(seconds: 60),
    );
    return asMap(res.data);
  }

  Future<Map<String, dynamic>> onboardStatus({
    required String service,
    required String workflowId,
  }) async {
    final res = await _api.get('/api/services/$service/onboard/$workflowId');
    return asMap(res.data);
  }

  Future<Map<String, dynamic>?> onboardLatest({
    required String service,
    required String environment,
  }) async {
    try {
      final res = await _api.get(
        '/api/services/$service/onboard/latest',
        query: {'environment': environment},
      );
      return asMap(res.data);
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, dynamic>> generateAllPayloads({
    required String service,
    required String environment,
    bool allowLlm = true,
    bool preferStored = true,
    int maxAttempts = 3,
  }) async {
    final res = await _api.post(
      '/api/payloads/generate-all',
      data: {
        'service': service,
        'environment': environment,
        'try_each': true,
        'write_back': true,
        'allow_llm': allowLlm,
        'prefer_stored': preferStored,
        'max_attempts': maxAttempts,
      },
      receiveTimeout: const Duration(minutes: 15),
    );
    return asMap(res.data);
  }

  /// Import Postman (or other adapter) collection + optional env into a payload set.
  Future<Map<String, dynamic>> importCollection({
    required String service,
    required Map<String, dynamic> collection,
    Map<String, dynamic>? environment,
    String format = 'postman',
    String? label,
    bool makeActive = true,
    bool bumpSet = true,
  }) async {
    final res = await _api.post(
      '/api/payloads/import',
      data: {
        'service': service,
        'collection': collection,
        if (environment != null) 'environment': environment,
        'format': format,
        if (label != null && label.isNotEmpty) 'label': label,
        'make_active': makeActive,
        'bump_set': bumpSet,
      },
      receiveTimeout: const Duration(minutes: 2),
    );
    return asMap(res.data);
  }
}
