import 'dart:convert';

/// Editable try-request draft for Postman-like Specs Test tab.
class TryDraft {
  const TryDraft({
    this.method = 'GET',
    this.path = '',
    this.body = '',
    this.bodyMode = 'json', // json | raw | none | multipart
    this.pathParams = const {},
    this.queryParams = const {},
    this.headers = const {},
    this.authBearer,
    this.fileFields = const {},
  });

  final String method;
  final String path;
  final String body;
  final String bodyMode;
  final Map<String, String> pathParams;
  final Map<String, String> queryParams;
  final Map<String, String> headers;
  final String? authBearer;
  /// field name -> local file path or browser filename marker
  final Map<String, String> fileFields;

  String get resolvedPath {
    var out = path;
    pathParams.forEach((k, v) {
      if (v.isEmpty) return;
      out = out.replaceAll('{$k}', v);
    });
    return out;
  }

  TryDraft copyWith({
    String? method,
    String? path,
    String? body,
    String? bodyMode,
    Map<String, String>? pathParams,
    Map<String, String>? queryParams,
    Map<String, String>? headers,
    String? authBearer,
    Map<String, String>? fileFields,
    bool clearAuth = false,
  }) {
    return TryDraft(
      method: method ?? this.method,
      path: path ?? this.path,
      body: body ?? this.body,
      bodyMode: bodyMode ?? this.bodyMode,
      pathParams: pathParams ?? this.pathParams,
      queryParams: queryParams ?? this.queryParams,
      headers: headers ?? this.headers,
      authBearer: clearAuth ? null : (authBearer ?? this.authBearer),
      fileFields: fileFields ?? this.fileFields,
    );
  }

  Map<String, dynamic> toJson() => {
        'method': method,
        'path': path,
        'body': body,
        'bodyMode': bodyMode,
        'pathParams': pathParams,
        'queryParams': queryParams,
        'headers': headers,
        'authBearer': authBearer,
        'fileFields': fileFields,
      };

  factory TryDraft.fromJson(Map<String, dynamic> json) {
    Map<String, String> strMap(dynamic v) {
      if (v is! Map) return {};
      return {
        for (final e in v.entries) '${e.key}': '${e.value ?? ''}',
      };
    }

    return TryDraft(
      method: '${json['method'] ?? 'GET'}'.toUpperCase(),
      path: '${json['path'] ?? ''}',
      body: '${json['body'] ?? ''}',
      bodyMode: '${json['bodyMode'] ?? 'json'}',
      pathParams: strMap(json['pathParams']),
      queryParams: strMap(json['queryParams']),
      headers: strMap(json['headers']),
      authBearer: json['authBearer']?.toString(),
      fileFields: strMap(json['fileFields']),
    );
  }

  TryDraft snapshot() => TryDraft.fromJson(jsonDecode(jsonEncode(toJson())) as Map<String, dynamic>);
}

/// Stack of drafts for refresh failure rollback.
class TryHistory {
  final List<TryDraft> _stack = [];

  bool get canRevert => _stack.isNotEmpty;

  void push(TryDraft draft) {
    _stack.add(draft.snapshot());
    if (_stack.length > 10) _stack.removeAt(0);
  }

  TryDraft? pop() {
    if (_stack.isEmpty) return null;
    return _stack.removeLast();
  }

  void clear() => _stack.clear();
}

final pathParamRe = RegExp(r'\{([^}/]+)\}');

Map<String, String> pathParamsFromTemplate(String path) {
  final out = <String, String>{};
  for (final m in pathParamRe.allMatches(path)) {
    out[m.group(1)!] = '';
  }
  return out;
}

String? formatJsonBody(String text) {
  final t = text.trim();
  if (t.isEmpty) return '';
  final decoded = jsonDecode(t);
  return const JsonEncoder.withIndent('  ').convert(decoded);
}

String buildCurl({
  required String method,
  required String url,
  required Map<String, String> headers,
  String? bearer,
  String? body,
  String bodyMode = 'json',
}) {
  final buf = StringBuffer('curl -sS -X ${method.toUpperCase()} ');
  buf.write("'${url.replaceAll("'", "'\\''")}'");
  final hdrs = Map<String, String>.from(headers);
  if (bearer != null && bearer.isNotEmpty) {
    hdrs.putIfAbsent('Authorization', () => 'Bearer $bearer');
  }
  if (bodyMode == 'json' && body != null && body.trim().isNotEmpty) {
    hdrs.putIfAbsent('Content-Type', () => 'application/json');
  }
  for (final e in hdrs.entries) {
    if (e.key.isEmpty) continue;
    final v = e.value.replaceAll("'", "'\\''");
    buf.write(" -H '${e.key}: $v'");
  }
  if (body != null && body.trim().isNotEmpty && bodyMode != 'none' && bodyMode != 'multipart') {
    final b = body.replaceAll("'", "'\\''");
    buf.write(" --data-raw '$b'");
  }
  return buf.toString();
}

String joinBasePath(String base, String path) {
  final b = base.trim().replaceAll(RegExp(r'/$'), '');
  var p = path.trim();
  if (p.isEmpty) return b;
  if (!p.startsWith('/')) p = '/$p';
  return '$b$p';
}

/// One changed field for before/after payload compare.
class DraftFieldChange {
  const DraftFieldChange({
    required this.field,
    required this.before,
    required this.after,
  });

  final String field;
  final String before;
  final String after;
}

List<DraftFieldChange> describeDraftDiff(TryDraft before, TryDraft after) {
  String mapStr(Map<String, String> m) {
    if (m.isEmpty) return '(empty)';
    final keys = m.keys.toList()..sort();
    return keys.map((k) => '$k=${m[k]}').join('\n');
  }

  final changes = <DraftFieldChange>[];
  void add(String field, String a, String b) {
    if (a == b) return;
    changes.add(DraftFieldChange(field: field, before: a, after: b));
  }

  add('method', before.method, after.method);
  add('path', before.path, after.path);
  add('bodyMode', before.bodyMode, after.bodyMode);
  add('body', before.body.trim().isEmpty ? '(empty)' : before.body, after.body.trim().isEmpty ? '(empty)' : after.body);
  add('pathParams', mapStr(before.pathParams), mapStr(after.pathParams));
  add('queryParams', mapStr(before.queryParams), mapStr(after.queryParams));
  add('headers', mapStr(before.headers), mapStr(after.headers));
  add('fileFields', mapStr(before.fileFields), mapStr(after.fileFields));
  return changes;
}

