part of 'run_detail_page.dart';

List<Map<String, dynamic>> _resultRows({
  required Map<String, dynamic> run,
  Object? results,
  List<Map<String, dynamic>> apis = const [],
}) {
  if (apis.isNotEmpty) return apis;
  final summary = run['api_summary'];
  if (summary is List) {
    return [
      for (final e in summary)
        if (e is Map) Map<String, dynamic>.from(e),
    ];
  }
  if (results is List) {
    return [
      for (final e in results)
        if (e is Map) Map<String, dynamic>.from(e),
    ];
  }
  if (results is Map) {
    final nested = results['apis'] ?? results['items'] ?? results['rows'];
    if (nested is List) {
      return [
        for (final e in nested)
          if (e is Map) Map<String, dynamic>.from(e),
      ];
    }
  }
  return const [];
}

num? _numOf(dynamic v) {
  if (v is num) return v;
  if (v is String) return num.tryParse(v);
  return null;
}

String _fmtMs(dynamic v) {
  final n = _numOf(v);
  if (n == null) return '—';
  return n.toStringAsFixed(n >= 100 ? 0 : 1);
}

/// Clean Playwright / stack errors for readable UI (strip ASCII boxes).
String _prettyError(String raw) {
  var text = raw
      .replaceAll(r'\n', '\n')
      .replaceAll(r'\r', '')
      .replaceAll('\r\n', '\n')
      .replaceAll('\r', '\n');
  final lines = text.split('\n');
  final out = <String>[];
  for (final line in lines) {
    final trimmed = line.trimRight();
    // Drop pure box-drawing / separator lines
    if (RegExp(r'^[-=_|+\\\s═║╔╗╚╝╠╣╟╢╤╧╪┌┐└┘├┤┬┴┼─│]+$').hasMatch(trimmed)) {
      continue;
    }
    // Strip leading/trailing box chars from content lines
    var cleaned = trimmed
        .replaceFirst(RegExp(r'^[|│║]\s?'), '')
        .replaceFirst(RegExp(r'\s?[|│║]\s*$'), '')
        .trimRight();
    if (cleaned.isEmpty) {
      if (out.isNotEmpty && out.last.isNotEmpty) out.add('');
      continue;
    }
    out.add(cleaned);
  }
  while (out.isNotEmpty && out.first.isEmpty) {
    out.removeAt(0);
  }
  while (out.isNotEmpty && out.last.isEmpty) {
    out.removeLast();
  }
  return out.join('\n');
}

/// Dataset version from run params / payloads_used (chip label: `vN`, `active`, or `—`).
String _payloadSetVersionLabel(Map<String, dynamic> run) {
  final params = _runParams(run);
  dynamic ver = params['payload_set_version'];
  if (ver == null) {
    final used = run['payloads_used'];
    if (used is Map) {
      final rp = used['run_params'];
      if (rp is Map) ver = rp['payload_set_version'];
      ver ??= used['payload_set_version'];
    }
  }
  if (ver == null) {
    final cfg = run['config'];
    if (cfg is Map) {
      ver = cfg['payload_set_version'];
      final payloads = cfg['payloads'];
      if (ver == null && payloads is Map) {
        ver = payloads['payload_set_version'];
      }
    }
  }
  if (ver == null) return '—';
  final s = '$ver'.trim();
  if (s.isEmpty || s == 'null') return '—';
  if (s == 'active') return 'active';
  if (s.startsWith('v')) return s;
  return 'v$s';
}

bool _apiRowFailed(Map<String, dynamic> a) {
  if (a['checks_passed'] == false || a['passed'] == false) return true;
  final fail = _intFrom(a['fail'] ?? a['fail_count'] ?? a['failed_count'] ?? a['ko'], 0);
  if (fail > 0) return true;
  final status = '${a['result'] ?? a['status'] ?? ''}'.toUpperCase();
  return status == 'FAIL' || status == 'FAILED' || status == 'ERROR';
}

String _apiRowLabel(Map<String, dynamic> a) =>
    '${a['api_id'] ?? a['id'] ?? a['name'] ?? a['path'] ?? ''}';

String _apiRowResultLabel(Map<String, dynamic> a) {
  if (a['checks_passed'] == true || a['passed'] == true) return 'PASS';
  if (a['checks_passed'] == false || a['passed'] == false) return 'FAIL';
  final st = a['result'] ?? a['outcome'];
  if (st != null && '$st'.isNotEmpty) return '$st';
  // Prefer not to show numeric HTTP status as "result".
  return '—';
}

String _httpStatusOf(Map<String, dynamic> a) {
  final v = a['http_status'] ?? a['status_code'] ?? a['status'];
  if (v is num) return '${v.toInt()}';
  if (v is String && int.tryParse(v) != null) return v;
  return '—';
}
