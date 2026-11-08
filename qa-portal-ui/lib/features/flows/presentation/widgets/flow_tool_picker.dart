import 'package:flutter/material.dart';

/// Dialog to pick an OpenAPI/MCP tool for a service and return a node stub.
///
/// Two-step UI: search/filter catalog services (folders), then tools.
Future<Map<String, dynamic>?> showFlowToolPicker(
  BuildContext context, {
  required Future<List<Map<String, dynamic>>> Function(String service) listTools,
  required Future<List<String>> Function() listServices,
  String initialService = 'am-subscription',
}) {
  return showDialog<Map<String, dynamic>>(
    context: context,
    builder: (ctx) => _FlowToolPickerDialog(
      listTools: listTools,
      listServices: listServices,
      initialService: initialService,
    ),
  );
}

class _FlowToolPickerDialog extends StatefulWidget {
  const _FlowToolPickerDialog({
    required this.listTools,
    required this.listServices,
    required this.initialService,
  });

  final Future<List<Map<String, dynamic>>> Function(String service) listTools;
  final Future<List<String>> Function() listServices;
  final String initialService;

  @override
  State<_FlowToolPickerDialog> createState() => _FlowToolPickerDialogState();
}

class _FlowToolPickerDialogState extends State<_FlowToolPickerDialog> {
  String? _service;
  var _loading = true;
  var _error = '';
  var _q = '';
  var _svcQ = '';
  List<String> _services = const [];
  List<Map<String, dynamic>> _tools = const [];

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    setState(() {
      _loading = true;
      _error = '';
    });
    try {
      final svcs = await widget.listServices();
      if (!mounted) return;
      var initial = widget.initialService;
      if (svcs.isNotEmpty && !svcs.contains(initial)) {
        initial = svcs.first;
      }
      setState(() {
        _services = svcs;
        _service = initial;
      });
      await _loadTools();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '$e';
      });
    }
  }

  Future<void> _loadTools() async {
    final svc = _service;
    if (svc == null || svc.isEmpty) return;
    setState(() {
      _loading = true;
      _error = '';
    });
    try {
      final rows = await widget.listTools(svc);
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

  List<String> get _filteredServices {
    final q = _svcQ.trim().toLowerCase();
    if (q.isEmpty) return _services;
    return _services.where((s) => s.toLowerCase().contains(q)).toList();
  }

  List<Map<String, dynamic>> get _filteredTools {
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
    final pickingService = _service == null;
    final rows = pickingService ? const <Map<String, dynamic>>[] : _filteredTools;
    final svcs = _filteredServices;

    return AlertDialog(
      title: Text(
        pickingService ? 'API Request — choose service' : 'Search for requests',
      ),
      content: SizedBox(
        width: 560,
        height: 520,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (!pickingService) ...[
              Row(
                children: [
                  TextButton.icon(
                    onPressed: () => setState(() {
                      _service = null;
                      _tools = const [];
                      _q = '';
                    }),
                    icon: const Icon(Icons.arrow_back, size: 16),
                    label: Text(_service ?? 'Services'),
                  ),
                  const Spacer(),
                ],
              ),
              TextField(
                decoration: const InputDecoration(
                  labelText: 'Search for requests',
                  isDense: true,
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.search, size: 18),
                ),
                onChanged: (v) => setState(() => _q = v),
              ),
            ] else ...[
              TextField(
                decoration: const InputDecoration(
                  labelText: 'Filter services',
                  isDense: true,
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.search, size: 18),
                ),
                onChanged: (v) => setState(() => _svcQ = v),
              ),
            ],
            const SizedBox(height: 8),
            if (_loading) const LinearProgressIndicator(minHeight: 2),
            if (_error.isNotEmpty)
              Text(
                _error,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            Expanded(
              child: pickingService
                  ? ListView.builder(
                      itemCount: svcs.length,
                      itemBuilder: (context, i) {
                        final s = svcs[i];
                        return ListTile(
                          dense: true,
                          leading: const Icon(Icons.folder_outlined, size: 20),
                          title: Text(s),
                          onTap: () {
                            setState(() => _service = s);
                            _loadTools();
                          },
                        );
                      },
                    )
                  : ListView.builder(
                      itemCount: rows.length,
                      itemBuilder: (context, i) {
                        final t = rows[i];
                        final name =
                            '${t['name'] ?? t['operation_id'] ?? 'tool'}';
                        final method =
                            '${t['method'] ?? 'GET'}'.toUpperCase();
                        final path = '${t['path'] ?? ''}';
                        final apiId = '${t['id'] ?? t['operation_id'] ?? name}';
                        return ListTile(
                          dense: true,
                          leading: Text(
                            method,
                            style: const TextStyle(
                              fontWeight: FontWeight.w700,
                              fontSize: 11,
                            ),
                          ),
                          title: Text(
                            name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          subtitle: Text(
                            path.isEmpty ? (_service ?? '') : path,
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
                              'payload_api_id': apiId,
                              'label': name,
                              'auth': !(_service == 'am-identity' &&
                                  name.toLowerCase().contains('login')),
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
