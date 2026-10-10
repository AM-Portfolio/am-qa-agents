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
