import 'dart:convert';

import '../../../specs/domain/openapi_fill.dart';
import '../../../specs/domain/try_draft.dart';

/// Never surface Dio/CORS/XHR stacks in the Try banner.
String softTryErr(String hint, Object e) {
  final s = '$e';
  final lower = s.toLowerCase();
  if (lower.contains('dioexception') ||
      lower.contains('xmlhttprequest') ||
      lower.contains('cors') ||
      lower.contains('connection errored') ||
      lower.contains('failed host lookup') ||
      lower.contains('socketexception')) {
    return '$hint — fill params and Send';
  }
  if (s.length > 120) return '$hint: ${s.substring(0, 117)}…';
  return '$hint: $s';
}

TryDraft withPathParamsFromTemplate(TryDraft draft) {
  final fromPath = pathParamsFromTemplate(draft.path);
  if (fromPath.isEmpty) return draft;
  final merged = <String, String>{
    for (final e in fromPath.entries) e.key: draft.pathParams[e.key] ?? e.value,
  };
  for (final e in draft.pathParams.entries) {
    merged.putIfAbsent(e.key, () => e.value);
  }
  return draft.copyWith(pathParams: merged);
}

String? versionFromRun(Map<String, dynamic> run) {
  final params = run['params'];
  dynamic ver;
  if (params is Map) ver = params['payload_set_version'];
  if (ver == null) {
    final used = run['payloads_used'];
    if (used is Map) {
      final rp = used['run_params'];
      if (rp is Map) ver = rp['payload_set_version'];
      ver ??= used['payload_set_version'];
    }
  }
  if (ver == null) return null;
  final s = '$ver'.trim();
  if (s.isEmpty || s == 'null' || s == 'active') return null;
  return s.startsWith('v') ? s.substring(1) : s;
}

String? rowFailureText(Map<String, dynamic> row) {
  final parts = <String>[];
  final err =
      '${row['error'] ?? row['error_message'] ?? row['message'] ?? ''}'.trim();
  if (err.isNotEmpty) parts.add(err);
  final body = row['response_body'] ?? row['response'] ?? row['body'];
  if (body != null && '$body'.trim().isNotEmpty) {
    final s = body is String ? body : prettyJsonValue(body);
    if (s.length > 800) {
      parts.add('${s.substring(0, 797)}…');
    } else {
      parts.add(s);
    }
  }
  final http = row['http_status'] ?? row['status_code'];
  if (http != null) parts.insert(0, 'HTTP $http');
  return parts.isEmpty ? null : parts.join('\n');
}

String prettyTryResponse(dynamic data) {
  if (data == null) return 'null';
  if (data is String) {
    final t = data.trim();
    if (t.isEmpty) return '';
    try {
      return prettyJsonValue(jsonDecode(t));
    } catch (_) {
      return data;
    }
  }
  return prettyJsonValue(data);
}

/// Flatten a run-API row into a request map for [applyRequestOntoDraft].
Map<String, dynamic> requestFromRow(Map<String, dynamic> row) {
  if (row['request'] is Map) {
    final req = Map<String, dynamic>.from(row['request'] as Map);
    req.putIfAbsent('method', () => row['method'] ?? row['http_method']);
    req.putIfAbsent(
      'path',
      () => row['path'] ?? row['url'] ?? row['path_template'],
    );
    req.putIfAbsent('path_params', () => row['path_params'] ?? row['pathParams']);
    req.putIfAbsent('query', () => row['query'] ?? row['query_params']);
    req.putIfAbsent('body', () => row['body'] ?? row['request_body']);
    req.putIfAbsent('headers', () => row['headers']);
    return req;
  }
  return {
    'method': row['method'] ?? row['http_method'],
    'path': row['path'] ?? row['url'] ?? row['path_template'],
    'query': row['query'] ?? row['query_params'],
    'path_params': row['path_params'] ?? row['pathParams'],
    'body': row['body'] ?? row['request_body'],
    'headers': row['headers'],
  };
}

/// True when path-param keys exist but values are empty, or mutating call has no body.
bool draftNeedsExampleFill(TryDraft draft) {
  final emptyPath = draft.pathParams.entries.any((e) => e.value.trim().isEmpty);
  if (emptyPath) return true;
  final m = draft.method.toUpperCase();
  if (m == 'GET' || m == 'DELETE' || m == 'HEAD') return false;
  if (draft.bodyMode == 'multipart') {
    return draft.fileFields.isEmpty;
  }
  return draft.body.trim().isEmpty && draft.bodyMode != 'none';
}

TryDraft normalizeBodyMode(TryDraft draft) {
  final m = draft.method.toUpperCase();
  if ((m == 'GET' || m == 'DELETE' || m == 'HEAD') &&
      draft.body.trim().isEmpty &&
      draft.bodyMode != 'multipart') {
    return draft.copyWith(bodyMode: 'none', body: '');
  }
  return draft;
}

/// Best-effort request map from a run trace row.
Map<String, dynamic>? requestFromTrace(Map<String, dynamic> trace) {
  final req = trace['request'];
  if (req is Map) {
    final out = Map<String, dynamic>.from(req);
    out.putIfAbsent('method', () => trace['method']);
    out.putIfAbsent('path', () => trace['path'] ?? trace['url']);
    return out;
  }
  final path = '${trace['path'] ?? trace['url'] ?? ''}'.trim();
  if (path.isEmpty) return null;
  return {
    'method': trace['method'],
    'path': path,
    'query': trace['query'],
    'path_params': trace['path_params'],
    'body': trace['body'],
    'headers': trace['headers'],
  };
}
