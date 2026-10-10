part of 'run_detail_page.dart';

bool _isPlaywrightRun(Map<String, dynamic> r) {
  final tt = '${r['test_type'] ?? ''}'.toLowerCase();
  final runner = '${r['runner'] ?? ''}'.toLowerCase();
  return tt == 'playwright' ||
      runner.contains('asrax-release-ops') ||
      runner.contains('ui-test');
}

bool _hasStructuredTrace(Map<String, dynamic> trace) {
  final req = trace['request'];
  final res = trace['response'];
  return req is Map || res is Map;
}

String _prettyJson(Object? value) {
  if (value == null) return '(empty)';
  try {
    if (value is String) {
      final t = value.trim();
      if (t.isEmpty) return '(empty)';
      try {
        return const JsonEncoder.withIndent('  ').convert(jsonDecode(t));
      } catch (_) {
        // Double-encoded JSON string (common in k6 traces)
        if ((t.startsWith('"') && t.endsWith('"')) || t.contains(r'\"')) {
          try {
            final once = jsonDecode(t);
            if (once is String) {
              return const JsonEncoder.withIndent('  ').convert(jsonDecode(once));
            }
            return const JsonEncoder.withIndent('  ').convert(once);
          } catch (_) {
            return value;
          }
        }
        return value;
      }
    }
    return const JsonEncoder.withIndent('  ').convert(value);
  } catch (_) {
    return '$value';
  }
}

Map<String, String> _stringHeaders(Object? raw) {
  if (raw is! Map) return {};
  final out = <String, String>{};
  for (final e in raw.entries) {
    final k = '${e.key}'.trim();
    if (k.isEmpty) continue;
    out[k] = '${e.value}';
  }
  return out;
}

String? _nonEmpty(Object? value) {
  if (value == null) return null;
  final s = '$value'.trim();
  return s.isEmpty ? null : s;
}

String _pathFromUrl(Object? url) {
  final raw = _nonEmpty(url);
  if (raw == null) return '';
  try {
    final uri = Uri.parse(raw);
    if (uri.hasScheme && uri.host.isNotEmpty) {
      final path = uri.path.isEmpty ? '/' : uri.path;
      return uri.hasQuery ? '$path?${uri.query}' : path;
    }
  } catch (_) {}
  return raw;
}

/// Human endpoint label for list + detail headers.
String _endpointLabel(Map<String, dynamic> t) {
  final path = _nonEmpty(t['path']) ?? _pathFromUrl(t['url']);
  final name = _nonEmpty(t['name']);
  final apiId = _nonEmpty(t['api_id']) ?? _nonEmpty(t['id']);
  // Prefer path; if name is just "METHOD path", skip duplicating method.
  if (path.isNotEmpty) return path;
  if (name != null) {
    final cleaned = name.replaceFirst(RegExp(r'^(GET|POST|PUT|PATCH|DELETE)\s+', caseSensitive: false), '');
    return cleaned.isNotEmpty ? cleaned : name;
  }
  if (apiId != null) return apiId;
  return _nonEmpty(t['url']) ?? '—';
}

String _traceUrl(Map<String, dynamic> t) {
  return _nonEmpty(t['url']) ??
      _nonEmpty(t['full_url']) ??
      _nonEmpty(t['path']) ??
      '';
}

Object? _traceStatus(Map<String, dynamic> t) {
  if (t['status_code'] != null) return t['status_code'];
  if (t['http_status'] != null) return t['http_status'];
  if (t['status'] is num || (t['status'] is String && int.tryParse('${t['status']}') != null)) {
    return t['status'];
  }
  if (t['response'] is Map) return (t['response'] as Map)['status'];
  return null;
}

String _bodyAsCurlData(Object? body) {
  if (body == null) return '';
  if (body is String) {
    final t = body.trim();
    if (t.isEmpty) return '';
    try {
      return const JsonEncoder.withIndent('  ').convert(jsonDecode(t));
    } catch (_) {
      return body;
    }
  }
  try {
    return const JsonEncoder.withIndent('  ').convert(body);
  } catch (_) {
    return '$body';
  }
}

String _shellDoubleQuote(String value) {
  return '"${value.replaceAll(r'\', r'\\').replaceAll('"', r'\"')}"';
}

String _curlFromTrace(Map<String, dynamic> trace) {
  final method = (_nonEmpty(trace['method']) ?? 'GET').toUpperCase();
  var url = _traceUrl(trace);
  if (url.isEmpty) return 'curl -sS -X $method';
  final req = trace['request'] is Map
      ? Map<String, dynamic>.from(trace['request'] as Map)
      : <String, dynamic>{};
  final headers = _stringHeaders(req['headers']);
  // Accept is useful default when traces omit headers
  if (headers.keys.every((k) => k.toLowerCase() != 'accept')) {
    headers.putIfAbsent('Accept', () => 'application/json');
  }
  final body = _bodyAsCurlData(req['body']);
  final parts = <String>[
    'curl',
    '-sS',
    '-X',
    method,
    _shellDoubleQuote(url),
  ];
  for (final e in headers.entries) {
    if (e.key.isEmpty) continue;
    parts.add('-H');
    parts.add(_shellDoubleQuote('${e.key}: ${e.value}'));
  }
  if (body.trim().isNotEmpty) {
    parts.add('--data-raw');
    parts.add(_shellDoubleQuote(body));
  }
  return parts.join(' ');
}

Color _statusColor(BuildContext context, Object? status) {
  final n = status is num ? status.toInt() : int.tryParse('$status');
  if (n == null) return Theme.of(context).colorScheme.outline;
  if (n >= 200 && n < 300) return Colors.green;
  if (n >= 400) return Theme.of(context).colorScheme.error;
  if (n >= 300) return Colors.orange;
  return Theme.of(context).colorScheme.outline;
}

bool _traceFailed(Map<String, dynamic> t) {
  final ok = t['ok'] ?? t['passed'] ?? t['checks_passed'];
  if (ok == false) return true;
  if (ok == true) return false;
  final code = _traceStatus(t);
  final n = code is num ? code.toInt() : int.tryParse('$code');
  return n != null && n >= 400;
}

