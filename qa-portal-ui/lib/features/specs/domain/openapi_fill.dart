import 'dart:convert';

import 'try_draft.dart';

/// Best-effort fill of path/query/header/body/file fields from an OpenAPI operation.
TryDraft seedDraftFromOpenApi({
  required Map<String, dynamic>? document,
  required String method,
  required String path,
  TryDraft base = const TryDraft(),
}) {
  final op = findOpenApiOperation(document, method: method, path: path);
  if (op == null) {
    return base.copyWith(
      method: method.toUpperCase(),
      path: path,
      pathParams: pathParamsFromTemplate(path).isEmpty
          ? base.pathParams
          : {
              ...pathParamsFromTemplate(path),
              ...base.pathParams,
            },
    );
  }

  final pathParams = <String, String>{...pathParamsFromTemplate(path)};
  final queryParams = <String, String>{...base.queryParams};
  final headers = <String, String>{...base.headers};
  final fileFields = <String, String>{...base.fileFields};
  var body = base.body;
  var bodyMode = base.bodyMode;

  final params = op['parameters'];
  if (params is List) {
    for (final raw in params) {
      if (raw is! Map) continue;
      final p = Map<String, dynamic>.from(raw);
      final name = '${p['name'] ?? ''}'.trim();
      if (name.isEmpty) continue;
      final loc = '${p['in'] ?? ''}'.toLowerCase();
      final value = _paramExample(p) ?? '';
      if (loc == 'path') {
        pathParams[name] = pathParams[name]?.isNotEmpty == true
            ? pathParams[name]!
            : value;
      } else if (loc == 'query') {
        queryParams.putIfAbsent(name, () => value);
      } else if (loc == 'header') {
        if (name.toLowerCase() == 'authorization') continue;
        headers.putIfAbsent(name, () => value);
      }
    }
  }

  final rb = op['requestBody'];
  if (rb is Map) {
    final content = rb['content'];
    if (content is Map) {
      if (content.containsKey('multipart/form-data')) {
        bodyMode = 'multipart';
        final schema = _schemaOf(content['multipart/form-data']);
        final props = schema?['properties'];
        if (props is Map) {
          props.forEach((k, v) {
            final name = '$k';
            if (v is Map &&
                ('${v['format']}' == 'binary' ||
                    '${v['type']}' == 'string' && '${v['format']}' == 'binary')) {
              fileFields.putIfAbsent(name, () => '');
            }
          });
        }
      } else if (content.containsKey('application/json')) {
        bodyMode = 'json';
        final example = _bodyExample(content['application/json']);
        if (example != null && body.trim().isEmpty) {
          body = prettyJsonValue(example);
        }
      } else if (content.isNotEmpty) {
        bodyMode = 'raw';
        final first = content.values.first;
        final example = _bodyExample(first);
        if (example != null && body.trim().isEmpty) {
          body = example is String ? example : prettyJsonValue(example);
        }
      }
    }
  } else if (method.toUpperCase() == 'GET' || method.toUpperCase() == 'DELETE') {
    if (body.trim().isEmpty) bodyMode = 'none';
  }

  // Prefer templated path from OAS if catalog gave a resolved path but we have params.
  var outPath = path;
  final template = op['_templatePath']?.toString();
  if (template != null && template.isNotEmpty && pathParams.isNotEmpty) {
    outPath = template;
  }

  return base.copyWith(
    method: method.toUpperCase(),
    path: outPath,
    pathParams: pathParams,
    queryParams: queryParams,
    headers: headers,
    body: body,
    bodyMode: bodyMode,
    fileFields: fileFields,
  );
}

/// Locate operation; attaches `_templatePath` on the returned map.
Map<String, dynamic>? findOpenApiOperation(
  Map<String, dynamic>? document, {
  required String method,
  required String path,
}) {
  if (document == null) return null;
  final paths = document['paths'];
  if (paths is! Map) return null;
  final m = method.toLowerCase();
  final normalized = _normPath(path);

  // Exact then template match
  Map<String, dynamic>? best;
  String? bestTemplate;

  for (final e in paths.entries) {
    final template = '${e.key}';
    final item = e.value;
    if (item is! Map) continue;
    final op = item[m] ?? item[method.toUpperCase()];
    if (op is! Map) continue;
    if (_normPath(template) == normalized || _pathMatchesTemplate(normalized, template)) {
      best = Map<String, dynamic>.from(op);
      bestTemplate = template;
      if (_normPath(template) == normalized) break;
    }
  }
  if (best == null) return null;
  best['_templatePath'] = bestTemplate;
  return best;
}

/// Path/query/header param name → OpenAPI enum values (if any).
Map<String, List<String>> extractParamEnums(
  Map<String, dynamic>? document, {
  required String method,
  required String path,
}) {
  final op = findOpenApiOperation(document, method: method, path: path);
  if (op == null) return const {};
  final out = <String, List<String>>{};
  final params = op['parameters'];
  if (params is! List) return out;
  for (final raw in params) {
    if (raw is! Map) continue;
    final p = Map<String, dynamic>.from(raw);
    final name = '${p['name'] ?? ''}'.trim();
    if (name.isEmpty) continue;
    final values = _paramEnumValues(p);
    if (values.isNotEmpty) out[name] = values;
  }
  return out;
}

List<String> _paramEnumValues(Map<String, dynamic> p) {
  List<String> from(dynamic raw) {
    if (raw is! List || raw.isEmpty) return const [];
    return [for (final e in raw) '$e'];
  }

  final top = from(p['enum']);
  if (top.isNotEmpty) return top;
  final schema = p['schema'];
  if (schema is Map) {
    final fromSchema = from(schema['enum']);
    if (fromSchema.isNotEmpty) return fromSchema;
    final items = schema['items'];
    if (items is Map) {
      final fromItems = from(items['enum']);
      if (fromItems.isNotEmpty) return fromItems;
    }
  }
  return const [];
}

String prettyJsonValue(Object? value) {
  if (value == null) return '';
  if (value is String) {
    final t = value.trim();
    if (t.isEmpty) return '';
    try {
      return const JsonEncoder.withIndent('  ').convert(jsonDecode(t));
    } catch (_) {
      return value;
    }
  }
  return const JsonEncoder.withIndent('  ').convert(value);
}

String? _paramExample(Map<String, dynamic> p) {
  if (p['example'] != null) return '${p['example']}';
  if (p['examples'] is Map && (p['examples'] as Map).isNotEmpty) {
    final first = (p['examples'] as Map).values.first;
    if (first is Map && first['value'] != null) return '${first['value']}';
  }
  final schema = p['schema'];
  if (schema is Map) {
    if (schema['example'] != null) return '${schema['example']}';
    if (schema['default'] != null) return '${schema['default']}';
    final enums = schema['enum'];
    if (enums is List && enums.isNotEmpty) return '${enums.first}';
  }
  return '';
}

Map<String, dynamic>? _schemaOf(dynamic media) {
  if (media is! Map) return null;
  final s = media['schema'];
  return s is Map ? Map<String, dynamic>.from(s) : null;
}

Object? _bodyExample(dynamic media) {
  if (media is! Map) return null;
  if (media['example'] != null) return media['example'];
  if (media['examples'] is Map && (media['examples'] as Map).isNotEmpty) {
    final first = (media['examples'] as Map).values.first;
    if (first is Map && first.containsKey('value')) return first['value'];
  }
  final schema = media['schema'];
  if (schema is Map) {
    if (schema['example'] != null) return schema['example'];
    return _exampleFromSchema(Map<String, dynamic>.from(schema));
  }
  return null;
}

Object? _exampleFromSchema(Map<String, dynamic> schema, [int depth = 0]) {
  if (depth > 4) return null;
  if (schema['example'] != null) return schema['example'];
  if (schema['default'] != null) return schema['default'];
  final type = '${schema['type'] ?? ''}';
  if (type == 'object' || schema['properties'] is Map) {
    final props = schema['properties'];
    if (props is! Map) return <String, dynamic>{};
    final out = <String, dynamic>{};
    props.forEach((k, v) {
      if (v is Map) {
        out['$k'] = _exampleFromSchema(Map<String, dynamic>.from(v), depth + 1);
      }
    });
    return out;
  }
  if (type == 'array') {
    final items = schema['items'];
    if (items is Map) {
      final one = _exampleFromSchema(Map<String, dynamic>.from(items), depth + 1);
      return one == null ? [] : [one];
    }
    return [];
  }
  if (type == 'integer' || type == 'number') return 0;
  if (type == 'boolean') return false;
  if (type == 'string') return '';
  return null;
}

String _normPath(String path) {
  var p = path.trim();
  if (p.isEmpty) return '/';
  if (!p.startsWith('/')) p = '/$p';
  if (p.length > 1 && p.endsWith('/')) p = p.substring(0, p.length - 1);
  // strip query
  final q = p.indexOf('?');
  if (q >= 0) p = p.substring(0, q);
  return p;
}

bool _pathMatchesTemplate(String concrete, String template) {
  final a = _normPath(concrete).split('/');
  final b = _normPath(template).split('/');
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    final t = b[i];
    if (t.startsWith('{') && t.endsWith('}')) continue;
    if (a[i] != t) return false;
  }
  return true;
}

/// Deep-ish copy of [document] with `example` filled from payload-set rows
/// (`path_params` / `query` / `body`) so Swagger Try shows the selected data version.
Map<String, dynamic>? openapiDocWithPayloadExamples(
  Map<String, dynamic>? document,
  List<Map<String, dynamic>> payloadRows,
) {
  if (document == null) return null;
  if (payloadRows.isEmpty) return document;
  final paths = document['paths'];
  if (paths is! Map) return document;

  final byOp = <String, Map<String, dynamic>>{};
  for (final row in payloadRows) {
    final method = '${row['method'] ?? ''}'.toUpperCase();
    final path = _normPath('${row['path'] ?? ''}');
    if (method.isEmpty || path.isEmpty) continue;
    final req = row['request'] is Map
        ? Map<String, dynamic>.from(row['request'] as Map)
        : row;
    byOp['$method $path'] = req;
  }
  if (byOp.isEmpty) return document;

  final newPaths = <String, dynamic>{};
  for (final e in paths.entries) {
    final template = '${e.key}';
    final item = e.value;
    if (item is! Map) {
      newPaths[template] = e.value;
      continue;
    }
    final newItem = Map<String, dynamic>.from(item);
    for (final methodKey in const [
      'get',
      'post',
      'put',
      'patch',
      'delete',
      'head',
      'options',
    ]) {
      final op = newItem[methodKey];
      if (op is! Map) continue;
      final method = methodKey.toUpperCase();
      Map<String, dynamic>? req;
      for (final entry in byOp.entries) {
        if (!entry.key.startsWith('$method ')) continue;
        final rowPath = entry.key.substring(method.length + 1);
        if (_normPath(rowPath) == _normPath(template) ||
            _pathMatchesTemplate(rowPath, template)) {
          req = entry.value;
          break;
        }
      }
      if (req == null) continue;
      newItem[methodKey] = _injectPayloadExamplesIntoOperation(
        Map<String, dynamic>.from(op),
        req,
      );
    }
    newPaths[template] = newItem;
  }

  return {
    ...document,
    'paths': newPaths,
  };
}

Map<String, dynamic> _injectPayloadExamplesIntoOperation(
  Map<String, dynamic> op,
  Map<String, dynamic> req,
) {
  final pathParams = <String, String>{};
  final queryParams = <String, String>{};
  final rawPath = req['path_params'] ?? req['pathParams'];
  if (rawPath is Map) {
    rawPath.forEach((k, v) {
      final s = '$v';
      if (s.isNotEmpty && !s.contains('{{')) pathParams['$k'] = s;
    });
  }
  final rawQuery = req['query'] ?? req['query_params'] ?? req['queryParams'];
  if (rawQuery is Map) {
    rawQuery.forEach((k, v) {
      final s = '$v';
      if (s.isNotEmpty && !s.contains('{{')) queryParams['$k'] = s;
    });
  }

  if (op['parameters'] is List &&
      (pathParams.isNotEmpty || queryParams.isNotEmpty)) {
    op['parameters'] = [
      for (final raw in op['parameters'] as List)
        _paramWithExample(
          raw,
          pathParams: pathParams,
          queryParams: queryParams,
        ),
    ];
  }

  final bodyRaw = req['body'] ?? req['json'] ?? req['data'];
  if (bodyRaw != null) {
    final rb = op['requestBody'];
    if (rb is Map) {
      final newRb = Map<String, dynamic>.from(rb);
      final content = newRb['content'];
      if (content is Map) {
        final newContent = Map<String, dynamic>.from(content);
        for (final mediaKey in newContent.keys.toList()) {
          final media = newContent[mediaKey];
          if (media is! Map) continue;
          final m = Map<String, dynamic>.from(media);
          m['example'] = bodyRaw;
          newContent[mediaKey] = m;
        }
        newRb['content'] = newContent;
        op['requestBody'] = newRb;
      }
    }
  }
  return op;
}

dynamic _paramWithExample(
  dynamic raw, {
  required Map<String, String> pathParams,
  required Map<String, String> queryParams,
}) {
  if (raw is! Map) return raw;
  final p = Map<String, dynamic>.from(raw);
  final name = '${p['name'] ?? ''}'.trim();
  final loc = '${p['in'] ?? ''}'.toLowerCase();
  String? ex;
  if (loc == 'path') {
    ex = pathParams[name];
  } else if (loc == 'query') {
    ex = queryParams[name];
  }
  if (ex == null || ex.isEmpty) return p;
  p['example'] = ex;
  final schema = p['schema'];
  if (schema is Map) {
    p['schema'] = {...Map<String, dynamic>.from(schema), 'example': ex};
  }
  return p;
}

/// Apply a catalog API row or saved payload request onto a draft (does not clear unspecified fields blindly).
TryDraft applyRequestOntoDraft(
  TryDraft base,
  Map<String, dynamic> request, {
  Map<String, dynamic>? openapiDoc,
}) {
  final method = '${request['method'] ?? base.method}'.toUpperCase();
  var path = '${request['path'] ?? request['url'] ?? base.path}';
  final pathParams = <String, String>{
    ...pathParamsFromTemplate(path),
    ...base.pathParams,
  };
  final rawPath =
      request['path_params'] ?? request['pathParams'];
  if (rawPath is Map) {
    rawPath.forEach((k, v) {
      final s = '$v';
      if (s.isNotEmpty) pathParams['$k'] = s;
    });
  }

  final queryParams = <String, String>{...base.queryParams};
  final rawQuery =
      request['query'] ?? request['query_params'] ?? request['queryParams'];
  if (rawQuery is Map && rawQuery.isNotEmpty) {
    queryParams.clear();
    rawQuery.forEach((k, v) {
      final s = '$v';
      if (s.isNotEmpty && !s.contains('{{')) queryParams['$k'] = s;
    });
  }

  final headers = <String, String>{...base.headers};
  final rawHeaders = request['headers'];
  if (rawHeaders is Map && rawHeaders.isNotEmpty) {
    rawHeaders.forEach((k, v) {
      final key = '$k';
      final s = '$v';
      if (key.toLowerCase() == 'authorization') return;
      if (s.contains('{{')) return;
      headers[key] = s;
    });
  }

  var bodyMode = '${request['body_mode'] ?? request['bodyMode'] ?? base.bodyMode}';
  final bodyRaw = request['body'] ?? request['json'] ?? request['data'];
  var body = base.body;
  if (bodyRaw == null) {
    // keep / none
  } else if (bodyRaw is String) {
    body = prettyJsonValue(bodyRaw);
    if (bodyMode == 'json' || body.trim().startsWith('{') || body.trim().startsWith('[')) {
      bodyMode = 'json';
    }
  } else {
    body = prettyJsonValue(bodyRaw);
    bodyMode = 'json';
  }
  if ((method == 'GET' || method == 'DELETE') &&
      (bodyRaw == null || (bodyRaw is String && bodyRaw.trim().isEmpty))) {
    bodyMode = 'none';
    body = '';
  }

  var draft = base.copyWith(
    method: method,
    path: path,
    pathParams: pathParams.isEmpty ? base.pathParams : pathParams,
    queryParams: queryParams,
    headers: {...base.headers, ...headers},
    body: body,
    bodyMode: bodyMode,
  );

  // Overlay OAS examples for any still-empty params / files
  draft = seedDraftFromOpenApi(
    document: openapiDoc,
    method: method,
    path: path,
    base: draft,
  );
  return draft;
}
