import 'dart:convert';
import 'package:flutter/material.dart';
import '../utils/flows_errors.dart';

part 'flow_node_compose_methods.part.dart';
part 'flow_node_compose_payload.part.dart';

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
