import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import '../../domain/try_draft.dart';
import 'kv_editor.dart';

/// Postman-like try workspace for the Specs Test tab.
class TestWorkspace extends StatefulWidget {
  const TestWorkspace({
    super.key,
    required this.draft,
    required this.loading,
    required this.tryResult,
    this.tryStatusCode,
    this.tryDurationMs,
    this.canRevert = false,
    this.selectedPayloadVersion,
    this.targetUrl,
    this.paramEnums = const {},
    required this.onDraftChanged,
    required this.onSend,
    required this.onMock,
    required this.onFormat,
    required this.onBuild,
    required this.onEnsure,
    required this.onRefreshPayload,
    required this.onRevert,
    required this.onCopyCurl,
    required this.onCopyResponse,
    required this.onSaveSet,
    required this.onPickFile,
    required this.onRemoveFile,
  });

  final TryDraft draft;
  final bool loading;
  final String? tryResult;
  final int? tryStatusCode;
  final int? tryDurationMs;
  final bool canRevert;
  final String? selectedPayloadVersion;
  final String? targetUrl;
  final Map<String, List<String>> paramEnums;
  final ValueChanged<TryDraft> onDraftChanged;
  final VoidCallback onSend;
  final VoidCallback onMock;
  final VoidCallback onFormat;
  final VoidCallback onBuild;
  final VoidCallback onEnsure;
  final VoidCallback onRefreshPayload;
  final VoidCallback onRevert;
  final VoidCallback onCopyCurl;
  final VoidCallback onCopyResponse;
  final VoidCallback onSaveSet;
  final Future<void> Function(String field) onPickFile;
  final void Function(String field) onRemoveFile;

  @override
  State<TestWorkspace> createState() => _TestWorkspaceState();
}

class _TestWorkspaceState extends State<TestWorkspace> {
  static const _methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];
  static const _bodyModes = ['json', 'raw', 'none', 'multipart'];

  int _queryAddCounter = 0;
  late final TextEditingController _newFileFieldCtrl;

  TryDraft get draft => widget.draft;

  @override
  void initState() {
    super.initState();
    _newFileFieldCtrl = TextEditingController();
  }

  @override
  void dispose() {
    _newFileFieldCtrl.dispose();
    super.dispose();
  }

  void _emit(TryDraft next) => widget.onDraftChanged(next);

  String _maskBearer(String? token) {
    if (token == null || token.isEmpty) return '(none)';
    if (token.length <= 10) return '••••••••';
    return '${token.substring(0, 4)}…${token.substring(token.length - 4)}';
  }

  void _addQueryParam() {
    _queryAddCounter += 1;
    final key = 'param$_queryAddCounter';
    final next = Map<String, String>.from(draft.queryParams);
    if (next.containsKey(key)) {
      _queryAddCounter += 1;
      next['param$_queryAddCounter'] = '';
    } else {
      next[key] = '';
    }
    _emit(draft.copyWith(queryParams: next));
  }

  void _setQueryEntry(String key, String value) {
    final next = Map<String, String>.from(draft.queryParams)..[key] = value;
    _emit(draft.copyWith(queryParams: next));
  }

  void _removeQuery(String key) {
    final next = Map<String, String>.from(draft.queryParams)..remove(key);
    _emit(draft.copyWith(queryParams: next));
  }

  void _setHeaderEntry(String key, String value) {
    final next = Map<String, String>.from(draft.headers)..[key] = value;
    _emit(draft.copyWith(headers: next));
  }

  void _removeHeader(String key) {
    final next = Map<String, String>.from(draft.headers)..remove(key);
    _emit(draft.copyWith(headers: next));
  }

  void _addHeader() {
    var i = draft.headers.length + 1;
    var key = 'Header$i';
    while (draft.headers.containsKey(key)) {
      i += 1;
      key = 'Header$i';
    }
    final next = Map<String, String>.from(draft.headers)..[key] = '';
    _emit(draft.copyWith(headers: next));
  }

  void _addFileField() {
    final name = _newFileFieldCtrl.text.trim();
    if (name.isEmpty) return;
    final next = Map<String, String>.from(draft.fileFields);
    next.putIfAbsent(name, () => '');
    _newFileFieldCtrl.clear();
    _emit(draft.copyWith(fileFields: next, bodyMode: 'multipart'));
  }

  TextStyle? get _mono => Theme.of(context).textTheme.bodySmall?.copyWith(
        fontFamily: 'monospace',
        fontFamilyFallback: const ['Courier New', 'monospace'],
      );

  @override
  Widget build(BuildContext context) {
    final saveLabel = widget.selectedPayloadVersion == null
        ? 'Save set'
        : 'Save to v${widget.selectedPayloadVersion}';
    final requestUrl = _requestUrl();

    return Padding(
      padding: const EdgeInsets.all(8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildTopBar(context),
          const SizedBox(height: 6),
          SelectableText(
            requestUrl,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  fontFamily: 'monospace',
                  color: AppColors.textSecondaryDark,
                ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final sideBySide = constraints.maxWidth >= 720;
                final editor = _buildEditorPane(context);
                final response = _buildResponsePane(context);
                if (sideBySide) {
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Expanded(flex: 3, child: editor),
                      const SizedBox(width: 8),
                      Expanded(flex: 2, child: response),
                    ],
                  );
                }
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(flex: 3, child: editor),
                    const SizedBox(height: 8),
                    Expanded(flex: 2, child: response),
                  ],
                );
              },
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              OutlinedButton(
                onPressed: widget.loading ? null : widget.onFormat,
                child: const Text('Format'),
              ),
              OutlinedButton(
                onPressed: widget.loading ? null : widget.onBuild,
                child: const Text('Build'),
              ),
              OutlinedButton(
                onPressed: widget.loading ? null : widget.onEnsure,
                child: const Text('Ensure'),
              ),
              OutlinedButton(
                onPressed: widget.loading ? null : widget.onRefreshPayload,
                child: const Text('Refresh payload'),
              ),
              if (widget.canRevert)
                OutlinedButton(
                  onPressed: widget.loading ? null : widget.onRevert,
                  child: const Text('Revert'),
                ),
              OutlinedButton(
                onPressed: widget.onCopyCurl,
                child: const Text('Copy curl'),
              ),
              OutlinedButton(
                onPressed: widget.tryResult == null ? null : widget.onCopyResponse,
                child: const Text('Copy response'),
              ),
              FilledButton.tonal(
                onPressed: widget.loading ? null : widget.onSaveSet,
                child: Text(saveLabel),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _requestUrl() {
    var path = draft.resolvedPath.trim();
    if (path.isEmpty) path = '/';
    if (!path.startsWith('/')) path = '/$path';
    final q = draft.queryParams.entries
        .where((e) => e.value.isNotEmpty)
        .map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}')
        .join('&');
    final base = (widget.targetUrl ?? '').trim();
    final joined = base.isEmpty ? path : joinBasePath(base, path);
    return q.isEmpty ? joined : '$joined?$q';
  }

  Widget _buildTopBar(BuildContext context) {
    final method = draft.method.toUpperCase();
    final color = methodColor(method);
    return Material(
      color: Theme.of(context).colorScheme.surface,
      child: LayoutBuilder(
        builder: (context, constraints) {
          return SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: ConstrainedBox(
              constraints: BoxConstraints(minWidth: constraints.maxWidth),
              child: Row(
                children: [
                  SizedBox(
                    width: 100,
                    child: DropdownButtonFormField<String>(
                      key: ValueKey('method-$method'),
                      initialValue: _methods.contains(method) ? method : 'GET',
                      decoration: InputDecoration(
                        isDense: true,
                        border: OutlineInputBorder(
                          borderSide: BorderSide(color: color, width: 1.5),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderSide: BorderSide(color: color, width: 1.5),
                        ),
                        contentPadding:
                            const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                      ),
                      selectedItemBuilder: (context) => [
                        for (final m in _methods)
                          Text(
                            m,
                            style: TextStyle(
                              color: methodColor(m),
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                      ],
                      items: [
                        for (final m in _methods)
                          DropdownMenuItem(
                            value: m,
                            child: Text(
                              m,
                              style: TextStyle(
                                color: methodColor(m),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                      ],
                      onChanged: widget.loading
                          ? null
                          : (v) {
                              if (v != null) _emit(draft.copyWith(method: v));
                            },
                    ),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(
                    width: (constraints.maxWidth - 280).clamp(160.0, 900.0),
                    child: TextFormField(
                      key: ValueKey('path-${draft.path}'),
                      initialValue: draft.path,
                      style: _mono,
                      decoration: const InputDecoration(
                        labelText: 'Path',
                        isDense: true,
                        border: OutlineInputBorder(),
                        contentPadding:
                            EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                      ),
                      onChanged: (v) {
                        final params = pathParamsFromTemplate(v);
                        final merged = <String, String>{
                          for (final k in params.keys) k: draft.pathParams[k] ?? '',
                        };
                        _emit(draft.copyWith(path: v, pathParams: merged));
                      },
                    ),
                  ),
                  if (widget.selectedPayloadVersion != null) ...[
                    const SizedBox(width: 6),
                    Chip(
                      label: Text(
                        'data v${widget.selectedPayloadVersion}',
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      visualDensity: VisualDensity.compact,
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      padding: EdgeInsets.zero,
                      labelPadding: const EdgeInsets.symmetric(horizontal: 6),
                    ),
                  ],
                  const SizedBox(width: 6),
                  FilledButton(
                    style: FilledButton.styleFrom(
                      visualDensity: VisualDensity.compact,
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                    ),
                    onPressed: widget.loading ? null : widget.onSend,
                    child: widget.loading
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : Text(
                            widget.selectedPayloadVersion == null
                                ? 'Send'
                                : 'Test v${widget.selectedPayloadVersion}',
                          ),
                  ),
                  const SizedBox(width: 6),
                  FilledButton.tonal(
                    style: FilledButton.styleFrom(
                      visualDensity: VisualDensity.compact,
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                    ),
                    onPressed: widget.loading ? null : widget.onMock,
                    child: const Text('Mock 1×'),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildEditorPane(BuildContext context) {
    return DefaultTabController(
      length: 5,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TabBar(
            isScrollable: true,
            labelColor: AppColors.primary,
            tabs: const [
              Tab(text: 'Params'),
              Tab(text: 'Headers'),
              Tab(text: 'Body'),
              Tab(text: 'Auth'),
              Tab(text: 'Files'),
            ],
          ),
          const SizedBox(height: 6),
          Expanded(
            child: TabBarView(
              children: [
                _buildParamsTab(context),
                _buildHeadersTab(context),
                _buildBodyTab(context),
                _buildAuthTab(context),
                _buildFilesTab(context),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildParamsTab(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.only(top: 4, right: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (draft.pathParams.isNotEmpty) ...[
            Text('Path params', style: Theme.of(context).textTheme.labelMedium),
            const SizedBox(height: 6),
            for (final e in draft.pathParams.entries)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: _paramValueField(
                  context,
                  label: '{${e.key}}',
                  name: e.key,
                  value: e.value,
                  onChanged: (v) {
                    final next = Map<String, String>.from(draft.pathParams)..[e.key] = v;
                    _emit(draft.copyWith(pathParams: next));
                  },
                ),
              ),
            const SizedBox(height: 8),
          ],
          Text('Query params', style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 6),
          for (final e in draft.queryParams.entries)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    flex: 2,
                    child: TextFormField(
                      key: ValueKey('qk-${e.key}'),
                      initialValue: e.key,
                      decoration: const InputDecoration(
                        labelText: 'Param',
                        isDense: true,
                        border: OutlineInputBorder(),
                      ),
                      onChanged: (nk) {
                        if (nk == e.key || nk.isEmpty) return;
                        final v = draft.queryParams[e.key] ?? '';
                        final next = Map<String, String>.from(draft.queryParams)
                          ..remove(e.key)
                          ..[nk] = v;
                        _emit(draft.copyWith(queryParams: next));
                      },
                    ),
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    flex: 3,
                    child: _paramValueField(
                      context,
                      label: 'Value',
                      name: e.key,
                      value: e.value,
                      onChanged: (v) => _setQueryEntry(e.key, v),
                    ),
                  ),
                  IconButton(
                    tooltip: 'Remove',
                    onPressed: () => _removeQuery(e.key),
                    icon: const Icon(Icons.close, size: 18),
                  ),
                ],
              ),
            ),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: _addQueryParam,
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Add'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _paramValueField(
    BuildContext context, {
    required String label,
    required String name,
    required String value,
    required ValueChanged<String> onChanged,
  }) {
    final enums = widget.paramEnums[name];
    if (enums != null && enums.isNotEmpty) {
      final options = <String>[...enums];
      if (value.isNotEmpty && !options.contains(value)) {
        options.insert(0, value);
      }
      final selected = options.contains(value)
          ? value
          : (options.isNotEmpty ? options.first : value);
      return DropdownButtonFormField<String>(
        key: ValueKey('enum-$name-$selected'),
        initialValue: selected.isEmpty && options.isNotEmpty ? options.first : selected,
        isExpanded: true,
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          border: const OutlineInputBorder(),
          helperText: 'enum',
          helperStyle: Theme.of(context).textTheme.labelSmall,
        ),
        items: [
          for (final o in options) DropdownMenuItem(value: o, child: Text(o)),
        ],
        onChanged: widget.loading
            ? null
            : (v) {
                if (v != null) onChanged(v);
              },
      );
    }
    return TextFormField(
      key: ValueKey('pv-$name-$value'),
      initialValue: value,
      decoration: InputDecoration(
        labelText: label,
        isDense: true,
        border: const OutlineInputBorder(),
      ),
      onChanged: onChanged,
    );
  }

  Widget _buildHeadersTab(BuildContext context) {
    final hasAuth = draft.authBearer != null && draft.authBearer!.isNotEmpty;
    return SingleChildScrollView(
      padding: const EdgeInsets.only(top: 4, right: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (hasAuth) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
              margin: const EdgeInsets.only(bottom: 8),
              decoration: BoxDecoration(
                color: Theme.of(context)
                    .colorScheme
                    .surfaceContainerHighest
                    .withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                  color: Theme.of(context).dividerColor.withValues(alpha: 0.4),
                ),
              ),
              child: Row(
                children: [
                  Icon(Icons.lock_outline, size: 14, color: AppColors.textSecondaryDark),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      'Authorization: Bearer ${_maskBearer(draft.authBearer)} (locked — managed by Auth tab)',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            ),
          ],
          KvEditor(
            entries: draft.headers,
            keyHint: 'Header',
            valueHint: 'Value',
            lockedKeys: hasAuth ? const {'Authorization'} : const {},
            onChanged: _setHeaderEntry,
            onRemove: _removeHeader,
            onAdd: _addHeader,
          ),
        ],
      ),
    );
  }

  Widget _buildBodyTab(BuildContext context) {
    final mode = draft.bodyMode;
    final showEditor = mode != 'none' && mode != 'multipart';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 160,
          child: DropdownButtonFormField<String>(
            key: ValueKey('bodyMode-$mode'),
            initialValue: _bodyModes.contains(mode) ? mode : 'json',
            decoration: const InputDecoration(
              labelText: 'Body mode',
              isDense: true,
              border: OutlineInputBorder(),
            ),
            items: [
              for (final m in _bodyModes)
                DropdownMenuItem(value: m, child: Text(m)),
            ],
            onChanged: (v) {
              if (v != null) _emit(draft.copyWith(bodyMode: v));
            },
          ),
        ),
        const SizedBox(height: 8),
        if (showEditor)
          Expanded(
            child: TextFormField(
              key: ValueKey('body-${draft.body.hashCode}-$mode'),
              initialValue: draft.body,
              maxLines: null,
              expands: true,
              textAlignVertical: TextAlignVertical.top,
              style: _mono,
              decoration: const InputDecoration(
                hintText: 'Request body',
                border: OutlineInputBorder(),
                alignLabelWithHint: true,
                contentPadding: EdgeInsets.all(10),
              ),
              onChanged: (v) => _emit(draft.copyWith(body: v)),
            ),
          )
        else
          Text(
            mode == 'multipart'
                ? 'Multipart body — attach files in the Files tab.'
                : 'No body will be sent.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
      ],
    );
  }

  Widget _buildAuthTab(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.only(top: 8, right: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Bearer token', style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 6),
          SelectableText(
            _maskBearer(draft.authBearer),
            style: _mono,
          ),
          const SizedBox(height: 10),
          Text(
            'SPT try-token is used for authenticated Try / Mock requests. '
            'The portal attaches the platform try-token when you Send.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppColors.textSecondaryDark,
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilesTab(BuildContext context) {
    final entries = draft.fileFields.entries.toList();
    return SingleChildScrollView(
      padding: const EdgeInsets.only(top: 4, right: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (entries.isEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                'No file fields yet. Add a field name, then pick a file.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          for (final e in entries)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: Text(e.key, style: Theme.of(context).textTheme.labelLarge),
                  ),
                  Expanded(
                    flex: 3,
                    child: Text(
                      e.value.isEmpty ? '(no file)' : e.value,
                      style: _mono,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  IconButton(
                    tooltip: 'Pick file',
                    onPressed: widget.loading
                        ? null
                        : () => widget.onPickFile(e.key),
                    icon: const Icon(Icons.attach_file, size: 18),
                  ),
                  IconButton(
                    tooltip: 'Remove',
                    onPressed: widget.loading
                        ? null
                        : () => widget.onRemoveFile(e.key),
                    icon: const Icon(Icons.close, size: 18),
                  ),
                ],
              ),
            ),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _newFileFieldCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Field name',
                    hintText: 'e.g. file',
                    isDense: true,
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: (_) => _addFileField(),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton.tonal(
                onPressed: _addFileField,
                child: const Text('Add field'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildResponsePane(BuildContext context) {
    final code = widget.tryStatusCode;
    final sc = statusColor(code, context);
    final duration = widget.tryDurationMs;
    final text = widget.tryResult ?? 'Send or Mock 1× to see result.';

    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context)
            .colorScheme
            .surfaceContainerHighest
            .withValues(alpha: 0.35),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: Theme.of(context).dividerColor.withValues(alpha: 0.45),
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            color: sc.withValues(alpha: 0.18),
            child: Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(color: sc, shape: BoxShape.circle),
                ),
                const SizedBox(width: 8),
                Text(
                  code == null ? 'Response' : 'HTTP $code',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: sc,
                        fontWeight: FontWeight.w700,
                      ),
                ),
                if (duration != null) ...[
                  const SizedBox(width: 10),
                  Text(
                    '${duration}ms',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppColors.textSecondaryDark,
                        ),
                  ),
                ],
                const Spacer(),
                Text(
                  'Response',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              ],
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: SingleChildScrollView(
                child: SelectableText(text, style: _mono),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
