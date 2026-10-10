import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';

import '../../domain/openapi_fill.dart';
import '../../domain/try_draft.dart';
import 'specs_cubit_host.mixin.dart';

mixin SpecsCubitTestMixin on SpecsCubitHost {
  void applyPayloadMap(Map<String, dynamic> payload, {bool pushHistory = true}) {
    if (pushHistory) pushDraftHistory();
    final request = payload['request'] is Map
        ? Map<String, dynamic>.from(payload['request'] as Map)
        : payload;
    final next = applyRequestOntoDraft(
      state.draft.copyWith(authBearer: state.tryToken ?? state.draft.authBearer),
      request,
      openapiDoc: state.openapiDoc,
    );
    // Pretty request body always when json
    final body = next.bodyMode == 'json' ? prettyJsonValue(next.body) : next.body;
    final enums = extractParamEnums(
      state.openapiDoc,
      method: next.method,
      path: next.path,
    );
    emit(
      state.copyWith(
        draft: next.copyWith(body: body),
        paramEnums: enums,
        canRevert: history.canRevert,
      ),
    );
  }

  /// Fill Test draft from catalog API row + OpenAPI examples, then overlay payload set.
  Future<void> applyApiToDraft(Map<String, dynamic> api, {bool pushHistory = true}) async {
    if (pushHistory) pushDraftHistory();
    final method = '${api['method'] ?? 'GET'}'.toUpperCase();
    final path = '${api['path'] ?? api['url'] ?? ''}';
    var draft = TryDraft(
      method: method,
      path: path,
      authBearer: state.tryToken,
      headers: const {'Accept': 'application/json'},
    );
    draft = applyRequestOntoDraft(draft, api, openapiDoc: state.openapiDoc);
    final enums = extractParamEnums(
      state.openapiDoc,
      method: draft.method,
      path: draft.path,
    );
    emit(
      state.copyWith(
        draft: draft.copyWith(
          body: draft.bodyMode == 'json' ? prettyJsonValue(draft.body) : draft.body,
        ),
        paramEnums: enums,
        canRevert: history.canRevert,
        clearTryResult: true,
        clearActionResult: true,
      ),
    );
    await loadSetApiIntoTry(pushHistory: false);
  }
  Future<void> pickTool(Map<String, dynamic> tool) async {
    final method = '${tool['method'] ?? ''}'.toUpperCase();
    final path = '${tool['path'] ?? ''}'.trim();
    final apiIdHint = '${tool['api_id'] ?? tool['op_id'] ?? ''}'.trim();
    Map<String, dynamic>? match;
    for (var i = 0; i < state.apis.length; i++) {
      final api = state.apis[i];
      final id = specsApiId(api, i);
      final apiMethod = '${api['method'] ?? ''}'.toUpperCase();
      final apiPath = '${api['path'] ?? api['path_template'] ?? ''}'.trim();
      final tpl = '${api['path_template'] ?? ''}'.trim();
      if (apiIdHint.isNotEmpty &&
          (id == apiIdHint ||
              '${api['operation_id'] ?? api['operationId'] ?? ''}' == apiIdHint)) {
        match = api;
        break;
      }
      if (apiMethod == method &&
          (apiPath == path || tpl == path || apiPath.contains(path) || path.contains(apiPath))) {
        match = api;
        break;
      }
    }
    if (match != null) {
      await pickApi(match);
      return;
    }
    emit(
      state.copyWith(
        draft: state.draft.copyWith(method: method.isEmpty ? 'GET' : method, path: path),
        message: 'Tool loaded into Test (no matching API row)',
      ),
    );
  }
  Future<void> pickApi(Map<String, dynamic> api) async {
    final index = state.apis.indexOf(api);
    emit(
      state.copyWith(
        selectedApiId: specsApiId(api, index < 0 ? 0 : index),
        clearTryResult: true,
        clearActionResult: true,
      ),
    );
    await applyApiToDraft(api);
  }

  /// Load set payload for selected API + version, then Send (single-click Test).
  Future<void> testApiOneClick([Map<String, dynamic>? api]) async {
    if (api != null) {
      await pickApi(api);
    } else if (state.selectedApiId != null) {
      final match = state.selectedApi;
      if (match != null) await applyApiToDraft(match, pushHistory: false);
      await loadSetApiIntoTry(pushHistory: false);
    }
    await runTry();
  }

  /// Test all checked APIs using the active payload set version.
  Future<void> testCheckedApis() async {
    final ids = state.selectedApiIds.isNotEmpty
        ? state.selectedApiIds.toList()
        : (state.selectedApiId != null ? [state.selectedApiId!] : <String>[]);
    if (ids.isEmpty) {
      emit(state.copyWith(message: 'Select at least one API to test'));
      return;
    }
    final lines = <String>[];
    var passed = 0;
    for (final id in ids) {
      Map<String, dynamic>? api;
      for (var i = 0; i < state.apis.length; i++) {
        if (specsApiId(state.apis[i], i) == id) {
          api = state.apis[i];
          break;
        }
      }
      if (api == null) {
        lines.add('$id — not found');
        continue;
      }
      await pickApi(api);
      await runTry();
      final code = state.tryStatusCode;
      final ok = code != null && code >= 200 && code < 300;
      if (ok) passed += 1;
      lines.add(
        '${ok ? 'PASS' : 'FAIL'} ${state.draft.method} ${state.draft.path} HTTP ${code ?? '—'}',
      );
    }
    emit(
      state.copyWith(
        actionResult: lines.join('\n'),
        message: 'Tested ${ids.length}: $passed passed',
      ),
    );
  }

  /// Run Use cases via execute config and return run id for navigation.
  Future<String?> runUseCases() async {
    return runLoad(mockOne: false);
  }

  void toggleApiSelection(String id, {required bool selected}) {
    final next = Set<String>.from(state.selectedApiIds);
    if (selected) {
      next.add(id);
    } else {
      next.remove(id);
    }
    emit(state.copyWith(selectedApiIds: next));
  }

  void selectAllApis() {
    final all = <String>{};
    for (var i = 0; i < state.apis.length; i++) {
      all.add(specsApiId(state.apis[i], i));
    }
    emit(state.copyWith(selectedApiIds: all));
  }

  void clearApiSelection() => emit(state.copyWith(selectedApiIds: const {}));
  Future<void> loadSetApiIntoTry({bool pushHistory = true}) async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    final id = state.selectedApiId;
    if (svc == null || ver == null || id == null) return;
    try {
      final set = await repo.getPayloadSet(svc, ver);
      final apis = set['apis'];
      if (apis is! Map) {
        emit(state.copyWith(message: 'Payload set v$ver has no APIs'));
        return;
      }
      final selected = state.selectedApi;
      final method = '${selected?['method'] ?? state.draft.method}'.toUpperCase();
      final path = '${selected?['path'] ?? selected?['path_template'] ?? state.draft.path}';
      final entry = findSetEntry(apis, apiId: id, method: method, path: path);
      if (entry != null) {
        applyPayloadMap(entry, pushHistory: pushHistory);
        emit(state.copyWith(message: 'Loaded payload from set v$ver'));
      } else {
        emit(
          state.copyWith(
            message: 'No payload in v$ver for $method $path ($id)',
          ),
        );
      }
    } catch (e) {
      emit(state.copyWith(message: 'Failed to load set v$ver: $e'));
    }
  }

  Future<void> formatBody() async {
    try {
      final formatted = formatJsonBody(state.draft.body);
      if (formatted == null) return;
      emit(state.copyWith(
        draft: state.draft.copyWith(body: formatted, bodyMode: 'json'),
        message: 'JSON formatted',
      ));
    } catch (e) {
      emit(state.copyWith(message: 'Invalid JSON: $e'));
    }
  }

  Future<void> refreshPayload() async {
    final before = state.draft.snapshot();
    pushDraftHistory();
    try {
      await ensureWorking(apply: true, pushHistory: false);
      final after = state.draft.snapshot();
      final diff = describeDraftDiff(before, after);
      emit(
        state.copyWith(
          lastPayloadDiff: diff,
          message: diff.isEmpty
              ? 'Refresh: no changes vs previous draft'
              : 'Refresh: ${diff.length} field(s) changed ? compare shown',
        ),
      );
    } catch (e) {
      final prev = history.pop();
      if (prev != null) {
        emit(state.copyWith(
          draft: prev,
          canRevert: history.canRevert,
          clearPayloadDiff: true,
          message: 'Refresh failed ? restored previous payload',
        ));
      } else {
        emit(state.copyWith(message: 'Refresh failed: $e', clearPayloadDiff: true));
      }
    }
  }

  void clearPayloadDiff() => emit(state.copyWith(clearPayloadDiff: true));
  Future<void> buildPayload({bool apply = true}) async {
    if (state.selectedService == null || state.draft.path.isEmpty) {
      emit(state.copyWith(actionResult: 'Select an API first'));
      return;
    }
    emit(state.copyWith(loading: true, clearActionResult: true));
    try {
      final out = await repo.buildPayload(
        service: state.selectedService!,
        environment: state.environment,
        method: state.draft.method,
        path: state.draft.path,
      );
      if (apply) applyPayloadMap(out);
      emit(state.copyWith(loading: false, actionResult: prettyJson(out)));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString()));
    }
  }

  Future<void> ensureWorking({bool apply = true, bool pushHistory = true}) async {
    if (state.selectedService == null || state.draft.path.isEmpty) {
      emit(state.copyWith(actionResult: 'Select an API first'));
      return;
    }
    emit(state.copyWith(loading: true, clearActionResult: true));
    try {
      final out = await repo.ensureWorking(
        service: state.selectedService!,
        environment: state.environment,
        method: state.draft.method,
        path: state.draft.path,
      );
      await loadPayloadSets(state.selectedService!);
      if (apply) applyPayloadMap(out, pushHistory: pushHistory);
      emit(state.copyWith(
        loading: false,
        actionResult: prettyJson(out),
        message: out['ok'] == true ? 'Working payload ready' : 'Ensure finished',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString()));
      rethrow;
    }
  }

  Future<void> prepareMcp() async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    emit(state.copyWith(loading: true, clearMcpSummary: true));
    try {
      final out = await repo.prepareMcp(service: svc, environment: state.environment);
      await loadPayloadSets(svc);
      try {
        await refreshOpenapiTools();
      } catch (_) {}
      emit(state.copyWith(
        loading: false,
        mcpSummary: {
          'mapped_count': out['mapped_count'],
          'skipped_count': out['skipped_count'],
          'mapped': out['mapped'],
          'skipped': out['skipped'],
          'portfolio_id': out['portfolio_id'],
        },
        message: 'MCP prepare done (${out['mapped_count'] ?? 0} mapped)',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, message: 'Prepare MCP failed: $e'));
    }
  }

  Future<void> aiMakeWork() async {
    pushDraftHistory();
    try {
      await ensureWorking(apply: true, pushHistory: false);
      await runTry();
    } catch (_) {
      revertDraft();
    }
  }

  Future<void> pickFile(String field) async {
    final result = await FilePicker.platform.pickFiles(withData: true);
    if (result == null || result.files.isEmpty) return;
    final f = result.files.first;
    final bytes = f.bytes;
    if (bytes == null) {
      emit(state.copyWith(message: 'Could not read file bytes'));
      return;
    }
    final files = Map<String, ({String name, List<int> bytes})>.from(state.fileBytes);
    files[field] = (name: f.name, bytes: bytes);
    final fields = Map<String, String>.from(state.draft.fileFields)..[field] = f.name;
    emit(state.copyWith(
      fileBytes: files,
      draft: state.draft.copyWith(fileFields: fields, bodyMode: 'multipart'),
    ));
  }

  void removeFile(String field) {
    final files = Map<String, ({String name, List<int> bytes})>.from(state.fileBytes)..remove(field);
    final fields = Map<String, String>.from(state.draft.fileFields)..remove(field);
    emit(state.copyWith(fileBytes: files, draft: state.draft.copyWith(fileFields: fields)));
  }

  String copyCurlText() {
    return _curlFromDraft(state.draft);
  }

  Map<String, dynamic> _requestOfRow(Map<String, dynamic> row) {
    if (row['request'] is Map) {
      return Map<String, dynamic>.from(row['request'] as Map);
    }
    return {
      'method': row['method'],
      'path': row['path'],
      'query': row['query'],
      'path_params': row['path_params'],
      'body': row['body'],
      'headers': row['headers'],
    };
  }

  Map<String, String> _strMap(dynamic raw) {
    if (raw is! Map) return {};
    return {
      for (final e in raw.entries)
        if ('${e.key}'.isNotEmpty) '${e.key}': '${e.value ?? ''}',
    };
  }

  String _curlFromDraft(TryDraft draft) {
    final target = (state.targetUrl ?? '').trim();
    var pathOnly = draft.resolvedPath.trim();
    if (pathOnly.isEmpty) pathOnly = '/';
    if (!pathOnly.startsWith('/')) pathOnly = '/$pathOnly';
    final q = draft.queryParams.entries
        .where((e) => e.value.isNotEmpty)
        .map(
          (e) =>
              '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}',
        )
        .join('&');
    final baseUrl = target.isNotEmpty
        ? joinBasePath(target, pathOnly)
        : 'https://{${state.selectedService ?? 'service'}-${state.environment}}$pathOnly';
    final url = q.isEmpty ? baseUrl : '$baseUrl?$q';
    final headers = Map<String, String>.from(draft.headers)
      ..putIfAbsent('Accept', () => 'application/json');
    return buildCurl(
      method: draft.method,
      url: url,
      headers: headers,
      bearer: state.tryToken ?? draft.authBearer,
      body: draft.body,
      bodyMode: draft.bodyMode,
    );
  }

  @override
  String curlForPayloadRow(Map<String, dynamic> row) {
    final req = _requestOfRow(row);
    final method = '${req['method'] ?? row['method'] ?? 'GET'}'.toUpperCase();
    final path = '${req['path'] ?? row['path'] ?? ''}';
    var body = '';
    final rawBody = req['body'];
    if (rawBody != null) {
      body = rawBody is String
          ? rawBody
          : const JsonEncoder.withIndent('  ').convert(rawBody);
    }
    final draft = TryDraft(
      method: method,
      path: path,
      pathParams: _strMap(req['path_params']),
      queryParams: _strMap(req['query'] ?? req['query_params']),
      headers: _strMap(req['headers']),
      body: body,
      bodyMode: body.trim().isEmpty ? 'none' : 'json',
      authBearer: state.tryToken,
    );
    return _curlFromDraft(draft);
  }

  @override
  Future<({int? status, int? ms, String body})> quickTestPayloadRow(
    Map<String, dynamic> row,
  ) async {
    applyPayloadMap(row, pushHistory: false);
    await runTry();
    final body = state.tryResult ?? '';
    final short = body.length > 240 ? '${body.substring(0, 237)}…' : body;
    return (status: state.tryStatusCode, ms: state.tryDurationMs, body: short);
  }

  Future<void> runTry() async {
    final svc = state.selectedService;
    final pathTemplate = state.draft.resolvedPath;
    if (svc == null || pathTemplate.isEmpty) {
      emit(state.copyWith(tryResult: 'Select service and path'));
      return;
    }
    if (pathParamRe.hasMatch(pathTemplate)) {
      emit(state.copyWith(tryResult: 'Fill path params: $pathTemplate', message: 'Unresolved path params'));
      return;
    }
    await ensureToken();
    emit(state.copyWith(loading: true, tryResult: null, error: null));
    final sw = Stopwatch()..start();
    try {
      Object? body;
      dynamic data;
      final headers = <String, dynamic>{
        ...state.draft.headers,
        if (state.tryToken != null && state.tryToken!.isNotEmpty)
          'Authorization': 'Bearer ${state.tryToken}',
      };

      if (state.draft.bodyMode == 'multipart' && state.fileBytes.isNotEmpty) {
        final form = FormData();
        state.fileBytes.forEach((field, file) {
          form.files.add(MapEntry(
            field,
            MultipartFile.fromBytes(file.bytes, filename: file.name),
          ));
        });
        if (state.draft.body.trim().isNotEmpty) {
          form.fields.add(MapEntry('payload', state.draft.body));
        }
        data = form;
      } else if (state.draft.bodyMode != 'none' && state.draft.body.trim().isNotEmpty) {
        if (state.draft.bodyMode == 'json') {
          body = jsonDecode(state.draft.body);
          headers.putIfAbsent('Content-Type', () => 'application/json');
        } else {
          body = state.draft.body;
        }
        data = body;
      }

      var path = pathTemplate.startsWith('/') ? pathTemplate.substring(1) : pathTemplate;
      if (state.draft.queryParams.isNotEmpty) {
        final q = state.draft.queryParams.entries
            .where((e) => e.value.isNotEmpty)
            .map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}')
            .join('&');
        if (q.isNotEmpty) path = '$path?$q';
      }
      final url = '/api/catalog/$svc/try/${state.environment}/$path';
      final res = await dio.request<dynamic>(
        url,
        data: data,
        options: Options(
          method: state.draft.method,
          headers: headers,
          validateStatus: (_) => true,
        ),
      );
      sw.stop();
      final prettyData = prettyResponseBody(res.data);
      emit(state.copyWith(
        loading: false,
        tryStatusCode: res.statusCode,
        tryDurationMs: sw.elapsedMilliseconds,
        tryResult: prettyData,
      ));
    } catch (e) {
      sw.stop();
      emit(state.copyWith(
        loading: false,
        tryDurationMs: sw.elapsedMilliseconds,
        tryResult: e.toString(),
      ));
    }
  }
}
