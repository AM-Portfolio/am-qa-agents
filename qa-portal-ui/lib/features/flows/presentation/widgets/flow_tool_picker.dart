import 'package:flutter/material.dart';

/// Dialog to pick an OpenAPI/MCP tool for a service and return a node stub.
Future<Map<String, dynamic>?> showFlowToolPicker(
  BuildContext context, {
  required Future<List<Map<String, dynamic>>> Function(String service) listTools,
  String initialService = 'am-subscription',
}) {
  return showDialog<Map<String, dynamic>>(
    context: context,
    builder: (ctx) => _FlowToolPickerDialog(
      listTools: listTools,
      initialService: initialService,
    ),
  );
}

class _FlowToolPickerDialog extends StatefulWidget {
  const _FlowToolPickerDialog({
    required this.listTools,
    required this.initialService,
  });

  final Future<List<Map<String, dynamic>>> Function(String service) listTools;
  final String initialService;

  @override
  State<_FlowToolPickerDialog> createState() => _FlowToolPickerDialogState();
}

class _FlowToolPickerDialogState extends State<_FlowToolPickerDialog> {
  late String _service;
  var _loading = true;
  var _error = '';
  var _q = '';
  List<Map<String, dynamic>> _tools = const [];

  @override
  void initState() {
    super.initState();
    _service = widget.initialService;
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = '';
    });
    try {
      final rows = await widget.listTools(_service);
      if (!mounted) return;
      setState(() {
        _tools = rows;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '$e';
        _tools = const [];
      });
    }
  }

  List<Map<String, dynamic>> get _filtered {
    final q = _q.trim().toLowerCase();
    if (q.isEmpty) return _tools;
    return _tools.where((t) {
      final blob =
          '${t['name'] ?? ''} ${t['method'] ?? ''} ${t['path'] ?? ''} ${t['summary'] ?? ''}'
              .toLowerCase();
      return blob.contains(q);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final rows = _filtered;
    return AlertDialog(
      title: const Text('Add API / MCP tool'),
      content: SizedBox(
        width: 520,
        height: 480,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            DropdownButtonFormField<String>(
              key: ValueKey('svc-$_service'),
              initialValue: _service,
              decoration: const InputDecoration(
                labelText: 'Service',
                border: OutlineInputBorder(),
                isDense: true,
              ),
              items: const [
                DropdownMenuItem(value: 'am-identity', child: Text('am-identity')),
                DropdownMenuItem(
                  value: 'am-subscription',
                  child: Text('am-subscription'),
                ),
              ],
              onChanged: (v) {
                if (v == null) return;
                setState(() => _service = v);
                _load();
              },
            ),
            const SizedBox(height: 8),
            TextField(
              decoration: const InputDecoration(
                labelText: 'Filter tools',
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
            Expanded(
              child: ListView.builder(
                itemCount: rows.length,
                itemBuilder: (context, i) {
                  final t = rows[i];
                  final name = '${t['name'] ?? t['operation_id'] ?? 'tool'}';
                  final method = '${t['method'] ?? 'GET'}'.toUpperCase();
                  final path = '${t['path'] ?? ''}';
                  return ListTile(
                    dense: true,
                    leading: Text(
                      method,
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 11,
                      ),
                    ),
                    title: Text(name, maxLines: 1, overflow: TextOverflow.ellipsis),
                    subtitle: Text(
                      path.isEmpty ? _service : path,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    onTap: () {
                      final safeId = name
                          .replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_')
                          .toLowerCase();
                      Navigator.pop(context, {
                        'id': 'node_$safeId',
                        'kind': 'call_tool',
                        'service': _service,
                        'method': method.toLowerCase(),
                        'path': path,
                        'exact_path': path.isNotEmpty ? path : null,
                        'tool_match': name,
                        'label': name,
                        'auth': _service != 'am-identity' ||
                            !name.toLowerCase().contains('login'),
                        'optional': false,
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
