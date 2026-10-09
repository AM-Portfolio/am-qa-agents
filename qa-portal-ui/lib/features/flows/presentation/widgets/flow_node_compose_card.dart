import 'dart:convert';

import 'package:flutter/material.dart';

import '../utils/flows_errors.dart';

enum _ComposeStage { service, api }

enum _DataPane { headers, body }

class FlowNodeComposeCard extends StatefulWidget {
  const FlowNodeComposeCard({
    super.key,
    required this.listTools,
    required this.listServices,
    required this.loadPayloadSet,
    required this.onCancel,
    required this.onConfirm,
    this.initialService = '',
  });

  final Future<List<Map<String, dynamic>>> Function(String service) listTools;
  final Future<List<String>> Function() listServices;
  final Future<Map<String, dynamic>?> Function(String service, {int? version})
      loadPayloadSet;
  final String initialService;
  final VoidCallback onCancel;
  final ValueChanged<Map<String, dynamic>> onConfirm;

  @override
  State<FlowNodeComposeCard> createState() => _FlowNodeComposeCardState();
}

class _FlowNodeComposeCardState extends State<FlowNodeComposeCard> {
  final _search = TextEditingController();
  final _headers = TextEditingController(text: '{\n}');
  final _body = TextEditingController(text: '{\n}');

  _ComposeStage _stage = _ComposeStage.service;
  var _loading = true;
  var _loadingTools = false;
  var _loadingPayload = false;
  var _error = '';
  List<String> _services = const [];
  List<Map<String, dynamic>> _tools = const [];
  String? _selectedService;
  Map<String, dynamic>? _selectedApi;
  int? _payloadVersion;
  List<_PayloadOpt> _payloads = const [];
  _PayloadOpt? _selectedPayload;
  _DataPane _dataPane = _DataPane.headers;

  bool get _bodyAllowed {
    final m = '${_selectedApi?['method'] ?? ''}'.toUpperCase();
    return m.isNotEmpty && m != 'GET' && m != 'HEAD';
  }

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  @override
  void dispose() {
    _search.dispose();
    _headers.dispose();
    _body.dispose();
    super.dispose();
  }

  Future<void> _bootstrap() async {
    setState(() {
      _loading = true;
      _error = '';
    });
    try {
      final svcs = await widget.listServices();
      if (!mounted) return;
      setState(() {
        _services = svcs;
        _loading = false;
      });
      final initial = widget.initialService.trim();
      if (initial.isNotEmpty && svcs.contains(initial)) {
        await _pickService(initial);
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = friendlyApiError(e);
      });
    }
  }

  Future<void> _pickService(String service) async {
    setState(() {
      _selectedService = service;
      _stage = _ComposeStage.api;
      _search.clear();
      _selectedApi = null;
      _selectedPayload = null;
      _payloads = const [];
      _loadingTools = true;
      _error = '';
    });
    try {
      final tools = await widget.listTools(service);
      if (!mounted) return;
      setState(() {
        _tools = tools;
        _loadingTools = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loadingTools = false;
        _error = friendlyApiError(e);
        _tools = const [];
      });
    }
  }

  Future<void> _pickApi(Map<String, dynamic> tool) async {
    final name = '${tool['name'] ?? tool['operation_id'] ?? 'tool'}';
    final method = '${tool['method'] ?? 'GET'}'.toUpperCase();
    final path = '${tool['path'] ?? ''}';
    final apiId = '${tool['id'] ?? tool['operation_id'] ?? name}';
    final stub = <String, dynamic>{
      'id': 'node_${name.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_').toLowerCase()}',
      'kind': 'call_tool',
      'service': _selectedService,
      'method': method.toLowerCase(),
      'path': path,
      if (path.isNotEmpty) 'exact_path': path,
      'tool_match': name,
      'payload_api_id': apiId,
      'label': name,
      'auth': !(_selectedService == 'am-identity' &&
          name.toLowerCase().contains('login')),
      'optional': false,
    };
    setState(() {
      _selectedApi = stub;
      _search.clear();
      _loadingPayload = true;
      _error = '';
      _dataPane = _DataPane.headers;
    });
    await _loadPayloads();
  }

  Future<void> _loadPayloads() async {
    final svc = _selectedService;
    if (svc == null || svc.isEmpty) return;
    setState(() {
      _loadingPayload = true;
      _error = '';
    });
    try {
      final ps = await widget.loadPayloadSet(svc, version: _payloadVersion);
      if (!mounted) return;
      final ver = ps?['version'];
      final apis = ps?['apis'];
      final rows = <_PayloadOpt>[];
      if (apis is Map) {
        for (final e in apis.entries) {
          final apiId = '${e.key}';
          final entry = e.value;
          if (entry is! Map) continue;
          final m = Map<String, dynamic>.from(entry);
          final req = m['request'] is Map
              ? Map<String, dynamic>.from(m['request'] as Map)
              : m;
          rows.add(
            _PayloadOpt(
              apiId: apiId,
              name: '${m['name'] ?? 'must_work'}',
              method: '${req['method'] ?? ''}'.toUpperCase(),
              path: '${req['path'] ?? ''}',
              request: req,
              bodyOverride: req['body'] is Map
                  ? Map<String, dynamic>.from(req['body'] as Map)
                  : null,
              headers: req['headers'] is Map
                  ? Map<String, dynamic>.from(req['headers'] as Map)
                  : null,
            ),
          );
        }
      }
      final preferred = '${_selectedApi?['payload_api_id'] ?? ''}';
      rows.sort((a, b) {
        if (preferred.isNotEmpty) {
          final am = a.apiId == preferred || a.apiId.contains(preferred);
          final bm = b.apiId == preferred || b.apiId.contains(preferred);
          if (am != bm) return am ? -1 : 1;
        }
        return a.apiId.compareTo(b.apiId);
      });
      setState(() {
        _payloads = rows;
        _payloadVersion = ver is int ? ver : int.tryParse('$ver') ?? _payloadVersion;
        _loadingPayload = false;
      });
      if (rows.isNotEmpty) {
        final match = rows.cast<_PayloadOpt?>().firstWhere(
              (r) =>
                  r != null &&
                  (r.apiId == preferred ||
                      (preferred.isNotEmpty && r.apiId.contains(preferred))),
              orElse: () => rows.first,
            );
        if (match != null) _applyPayload(match);
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loadingPayload = false;
        _error = '$e';
        _payloads = const [];
      });
    }
  }

  void _applyPayload(_PayloadOpt opt) {
    setState(() {
      _selectedPayload = opt;
      _headers.text = const JsonEncoder.withIndent('  ').convert(opt.headers ?? {});
      _body.text = const JsonEncoder.withIndent('  ')
          .convert(opt.bodyOverride ?? {});
      if (_selectedApi != null) {
        _selectedApi = {
          ..._selectedApi!,
          'payload_api_id': opt.apiId,
          'payload_name': opt.name,
          if (opt.path.isNotEmpty) 'path': opt.path,
          if (opt.path.isNotEmpty) 'exact_path': opt.path,
          if (opt.method.isNotEmpty) 'method': opt.method.toLowerCase(),
        };
      }
    });
  }

  void _clearService() {
    setState(() {
      _selectedService = null;
      _selectedApi = null;
      _selectedPayload = null;
      _tools = const [];
      _payloads = const [];
      _stage = _ComposeStage.service;
      _search.clear();
      _headers.text = '{\n}';
      _body.text = '{\n}';
    });
  }

  List<String> get _serviceSuggestions {
    final q = _search.text.trim().toLowerCase();
    if (q.isEmpty) return _services.take(40).toList();
    return _services
        .where((s) => s.toLowerCase().contains(q))
        .take(40)
        .toList();
  }

  List<Map<String, dynamic>> get _apiSuggestions {
    final q = _search.text.trim().toLowerCase();
    if (q.isEmpty) return _tools;
    return _tools.where((t) {
      final blob =
          '${t['name'] ?? ''} ${t['method'] ?? ''} ${t['path'] ?? ''} ${t['summary'] ?? ''}'
              .toLowerCase();
      return blob.contains(q);
    }).toList();
  }

  void _confirm() {
    final api = _selectedApi;
    if (api == null) {
      setState(() => _error = 'Select an API first');
      return;
    }
    setState(() => _error = '');
    Map<String, dynamic>? headers;
    Map<String, dynamic>? body;
    try {
      final ht = _headers.text.trim();
      if (ht.isNotEmpty && ht != '{}') {
        final v = jsonDecode(ht);
        if (v is! Map) {
          setState(() => _error = 'Headers must be a JSON object');
          return;
        }
        headers = Map<String, dynamic>.from(v);
      }
      if (_bodyAllowed) {
        final bt = _body.text.trim();
        if (bt.isNotEmpty && bt != '{}') {
          final v = jsonDecode(bt);
          if (v is! Map) {
            setState(() => _error = 'Body must be a JSON object');
            return;
          }
          body = Map<String, dynamic>.from(v);
        }
      }
    } catch (_) {
      setState(() => _error = 'Invalid headers/body JSON');
      return;
    }
    final stub = <String, dynamic>{
      ...api,
      if (_selectedPayload != null) ...{
        'payload_api_id': _selectedPayload!.apiId,
        'payload_name': _selectedPayload!.name,
      },
      if (_payloadVersion != null) 'payload_set_version': _payloadVersion,
      if (body != null) 'body_override': body,
      if (headers != null && headers.isNotEmpty) 'headers': headers,
    };
    widget.onConfirm(stub);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final suggestions = _stage == _ComposeStage.service
        ? _serviceSuggestions
        : const <String>[];
    final apiRows =
        _stage == _ComposeStage.api && _selectedApi == null ? _apiSuggestions : const <Map<String, dynamic>>[];

    return SizedBox(
      width: 320,
      child: Card(
        elevation: 1,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: BorderSide(color: cs.primary, width: 2),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 4, 6),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: cs.primary.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'NEW',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Add step',
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                IconButton(
                  tooltip: 'Close',
                  visualDensity: VisualDensity.compact,
                  onPressed: widget.onCancel,
                  icon: const Icon(Icons.close, size: 18),
                ),
              ],
            ),
          ),
          if (_loading) const LinearProgressIndicator(minHeight: 2),
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 420),
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
              child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (_selectedService != null)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: InputChip(
                      avatar: const Icon(Icons.domain_outlined, size: 16),
                      label: Text(_selectedService!),
                      onDeleted: _clearService,
                    ),
                  ),
                TextField(
                  controller: _search,
                  decoration: InputDecoration(
                    hintText: _stage == _ComposeStage.service
                        ? 'Search services…'
                        : (_selectedApi == null
                            ? 'Search APIs…'
                            : 'Filter payloads / refine…'),
                    isDense: true,
                    border: const OutlineInputBorder(),
                    prefixIcon: const Icon(Icons.search, size: 18),
                  ),
                  onChanged: (_) => setState(() {}),
                ),
                if (_loadingTools || _loadingPayload)
                  const Padding(
                    padding: EdgeInsets.only(top: 4),
                    child: LinearProgressIndicator(minHeight: 2),
                  ),
                if (_error.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          _error,
                          style: TextStyle(color: cs.error, fontSize: 12),
                        ),
                        if (_stage == _ComposeStage.api &&
                            _selectedService != null)
                          Align(
                            alignment: Alignment.centerLeft,
                            child: TextButton.icon(
                              onPressed: _loadingTools
                                  ? null
                                  : () => _pickService(_selectedService!),
                              icon: const Icon(Icons.refresh, size: 16),
                              label: const Text('Retry'),
                            ),
                          ),
                      ],
                    ),
                  ),
                if (_stage == _ComposeStage.service && !_loading)
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxHeight: 180),
                    child: ListView.builder(
                      shrinkWrap: true,
                      itemCount: suggestions.length,
                      itemBuilder: (context, i) {
                        final s = suggestions[i];
                        return ListTile(
                          dense: true,
                          leading: const Icon(Icons.folder_outlined, size: 18),
                          title: Text(s),
                          onTap: () => _pickService(s),
                        );
                      },
                    ),
                  ),
                if (_stage == _ComposeStage.api &&
                    _selectedApi == null &&
                    !_loadingTools)
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxHeight: 200),
                    child: ListView.builder(
                      shrinkWrap: true,
                      itemCount: apiRows.length,
                      itemBuilder: (context, i) {
                        final t = apiRows[i];
                        final name =
                            '${t['name'] ?? t['operation_id'] ?? 'tool'}';
                        final method =
                            '${t['method'] ?? 'GET'}'.toUpperCase();
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
                          title: Text(
                            name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          subtitle: Text(
                            path,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          onTap: () => _pickApi(t),
                        );
                      },
                    ),
                  ),
                if (_selectedApi != null) ...[
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: cs.outlineVariant),
                      color: cs.primaryContainer.withValues(alpha: 0.25),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: cs.primary.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                '${_selectedApi!['method'] ?? ''}'
                                    .toString()
                                    .toUpperCase(),
                                style: const TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                '${_selectedApi!['label']}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            IconButton(
                              tooltip: 'Change API',
                              visualDensity: VisualDensity.compact,
                              icon: const Icon(Icons.edit_outlined, size: 18),
                              onPressed: () => setState(() {
                                _selectedApi = null;
                                _selectedPayload = null;
                              }),
                            ),
                          ],
                        ),
                        Text(
                          '${_selectedApi!['service']} · ${_selectedApi!['path'] ?? ''}',
                          style: theme.textTheme.bodySmall,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Text('Payload', style: theme.textTheme.labelLarge),
                      const Spacer(),
                      Text(
                        _payloadVersion == null
                            ? 'latest'
                            : 'v$_payloadVersion',
                        style: theme.textTheme.labelSmall,
                      ),
                      IconButton(
                        tooltip: 'Reload payloads',
                        onPressed: _loadPayloads,
                        icon: const Icon(Icons.refresh, size: 18),
                      ),
                    ],
                  ),
                  if (_payloads.isNotEmpty)
                    DropdownButtonFormField<_PayloadOpt>(
                      initialValue: _selectedPayload,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Payload entry',
                        isDense: true,
                        border: OutlineInputBorder(),
                      ),
                      items: [
                        for (final p in _payloads)
                          DropdownMenuItem(
                            value: p,
                            child: Text(
                              '${p.apiId} · ${p.name}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                      ],
                      onChanged: (p) {
                        if (p != null) _applyPayload(p);
                      },
                    ),
                  const SizedBox(height: 10),
                  if (_bodyAllowed)
                    SegmentedButton<_DataPane>(
                      segments: const [
                        ButtonSegment(
                          value: _DataPane.headers,
                          label: Text('Headers'),
                          icon: Icon(Icons.view_headline, size: 16),
                        ),
                        ButtonSegment(
                          value: _DataPane.body,
                          label: Text('Body'),
                          icon: Icon(Icons.data_object, size: 16),
                        ),
                      ],
                      selected: {_dataPane},
                      onSelectionChanged: (s) {
                        if (s.isEmpty) return;
                        setState(() => _dataPane = s.first);
                      },
                    )
                  else
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        'Headers',
                        style: theme.textTheme.labelLarge,
                      ),
                    ),
                  const SizedBox(height: 8),
                  SizedBox(
                    height: 200,
                    child: TextField(
                      key: ValueKey(_bodyAllowed && _dataPane == _DataPane.body
                          ? 'body'
                          : 'headers'),
                      controller: !_bodyAllowed ||
                              _dataPane == _DataPane.headers
                          ? _headers
                          : _body,
                      maxLines: null,
                      expands: true,
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 12,
                      ),
                      decoration: InputDecoration(
                        isDense: true,
                        border: const OutlineInputBorder(),
                        hintText: !_bodyAllowed ||
                                _dataPane == _DataPane.headers
                            ? '{\n  "Authorization": "…"\n}'
                            : '{\n  "key": "value"\n}',
                      ),
                    ),
                  ),
                ],
              ],
            ),
            ),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 6, 10, 10),
            child: Row(
              children: [
                TextButton(
                  onPressed: widget.onCancel,
                  child: const Text('Cancel'),
                ),
                const Spacer(),
                FilledButton(
                  onPressed: _selectedApi == null ? null : _confirm,
                  child: const Text('Add to flow'),
                ),
              ],
            ),
          ),
          ],
        ),
      ),
    );
  }
}

class _PayloadOpt {
  const _PayloadOpt({
    required this.apiId,
    required this.name,
    required this.method,
    required this.path,
    required this.request,
    this.bodyOverride,
    this.headers,
  });

  final String apiId;
  final String name;
  final String method;
  final String path;
  final Map<String, dynamic> request;
  final Map<String, dynamic>? bodyOverride;
  final Map<String, dynamic>? headers;

  @override
  bool operator ==(Object other) =>
      other is _PayloadOpt && other.apiId == apiId && other.name == name;

  @override
  int get hashCode => Object.hash(apiId, name);
}
