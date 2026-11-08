import 'package:flutter/material.dart';

/// Pick a payload-set entry for a bound API node.
Future<Map<String, dynamic>?> showFlowPayloadPicker(
  BuildContext context, {
  required Future<Map<String, dynamic>?> Function() loadPayloadSet,
  String? preferredApiId,
  String? method,
  String? path,
}) {
  return showDialog<Map<String, dynamic>>(
    context: context,
    builder: (ctx) => _FlowPayloadPickerDialog(
      loadPayloadSet: loadPayloadSet,
      preferredApiId: preferredApiId,
      method: method,
      path: path,
    ),
  );
}

class _FlowPayloadPickerDialog extends StatefulWidget {
  const _FlowPayloadPickerDialog({
    required this.loadPayloadSet,
    this.preferredApiId,
    this.method,
    this.path,
  });

  final Future<Map<String, dynamic>?> Function() loadPayloadSet;
  final String? preferredApiId;
  final String? method;
  final String? path;

  @override
  State<_FlowPayloadPickerDialog> createState() =>
      _FlowPayloadPickerDialogState();
}

class _FlowPayloadPickerDialogState extends State<_FlowPayloadPickerDialog> {
  var _loading = true;
  var _error = '';
  var _q = '';
  List<_PayloadRow> _rows = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = '';
    });
    try {
      final ps = await widget.loadPayloadSet();
      if (!mounted) return;
      final apis = ps?['apis'];
      final rows = <_PayloadRow>[];
      if (apis is Map) {
        for (final e in apis.entries) {
          final apiId = '${e.key}';
          final entry = e.value;
          if (entry is! Map) continue;
          final m = Map<String, dynamic>.from(entry);
          final req = m['request'] is Map
              ? Map<String, dynamic>.from(m['request'] as Map)
              : m;
          final name = '${m['name'] ?? 'must_work'}';
          final method = '${req['method'] ?? ''}'.toUpperCase();
          final path = '${req['path'] ?? ''}';
          rows.add(
            _PayloadRow(
              apiId: apiId,
              name: name,
              method: method,
              path: path,
              request: req,
              bodyOverride: req['body'] is Map
                  ? Map<String, dynamic>.from(req['body'] as Map)
                  : null,
            ),
          );
        }
      }
      rows.sort((a, b) {
        final pref = widget.preferredApiId ?? '';
        if (pref.isNotEmpty) {
          final am = a.apiId == pref || a.apiId.contains(pref);
          final bm = b.apiId == pref || b.apiId.contains(pref);
          if (am != bm) return am ? -1 : 1;
        }
        return a.apiId.compareTo(b.apiId);
      });
      setState(() {
        _rows = rows;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '$e';
      });
    }
  }

  List<_PayloadRow> get _filtered {
    final q = _q.trim().toLowerCase();
    var rows = _rows;
    final method = (widget.method ?? '').toUpperCase();
    final path = widget.path ?? '';
    if (method.isNotEmpty || path.isNotEmpty) {
      final pathHits = rows
          .where(
            (r) =>
                (method.isEmpty || r.method == method) &&
                (path.isEmpty ||
                    r.path == path ||
                    r.path.contains(path) ||
                    path.contains(r.path)),
          )
          .toList();
      if (pathHits.isNotEmpty) rows = pathHits;
    }
    if (q.isEmpty) return rows;
    return rows
        .where(
          (r) =>
              '${r.apiId} ${r.name} ${r.method} ${r.path}'.toLowerCase().contains(
                    q,
                  ),
        )
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final rows = _filtered;
    return AlertDialog(
      title: const Text('Choose data for API'),
      content: SizedBox(
        width: 560,
        height: 480,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              decoration: const InputDecoration(
                labelText: 'Filter payloads',
                isDense: true,
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.search, size: 18),
              ),
              onChanged: (v) => setState(() => _q = v),
            ),
            const SizedBox(height: 8),
            if (_loading) const LinearProgressIndicator(minHeight: 2),
            if (_error.isNotEmpty)
              Text(
                _error,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            if (!_loading && rows.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('No payload-set entries for this service.'),
              ),
            Expanded(
              child: ListView.builder(
                itemCount: rows.length,
                itemBuilder: (context, i) {
                  final r = rows[i];
                  return ListTile(
                    dense: true,
                    leading: Text(
                      r.method.isEmpty ? '?' : r.method,
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 11,
                      ),
                    ),
                    title: Text(
                      '${r.apiId} · ${r.name}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text(
                      r.path,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    onTap: () {
                      Navigator.pop(context, {
                        'payload_api_id': r.apiId,
                        'payload_name': r.name,
                        if (r.bodyOverride != null)
                          'body_override': r.bodyOverride,
                        if (r.path.isNotEmpty) 'path': r.path,
                        if (r.path.isNotEmpty) 'exact_path': r.path,
                        if (r.method.isNotEmpty)
                          'method': r.method.toLowerCase(),
                      });
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
      ],
    );
  }
}

class _PayloadRow {
  const _PayloadRow({
    required this.apiId,
    required this.name,
    required this.method,
    required this.path,
    required this.request,
    this.bodyOverride,
  });

  final String apiId;
  final String name;
  final String method;
  final String path;
  final Map<String, dynamic> request;
  final Map<String, dynamic>? bodyOverride;
}
