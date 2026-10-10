part of 'flow_node_compose_card.dart';

extension FlowNodeComposeMethods on _FlowNodeComposeCardState {
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
}
