import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import '../../domain/try_draft.dart';
import 'kv_editor.dart';
import 'test_auth_panel.dart';

/// Request editor tabs (Params / Headers / Body / Auth / Files) for [TestWorkspace].
class TestRequestPanel extends StatefulWidget {
  const TestRequestPanel({
    super.key,
    required this.draft,
    required this.loading,
    this.paramEnums = const {},
    required this.onDraftChanged,
    required this.onPickFile,
    required this.onRemoveFile,
  });

  final TryDraft draft;
  final bool loading;
  final Map<String, List<String>> paramEnums;
  final ValueChanged<TryDraft> onDraftChanged;
  final Future<void> Function(String field) onPickFile;
  final void Function(String field) onRemoveFile;

  @override
  State<TestRequestPanel> createState() => _TestRequestPanelState();
}

class _TestRequestPanelState extends State<TestRequestPanel> {
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

  TextStyle? get _mono => Theme.of(context).textTheme.bodySmall?.copyWith(
        fontFamily: 'monospace',
        fontFamilyFallback: const ['Courier New', 'monospace'],
      );

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

  @override
  Widget build(BuildContext context) {
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
                TestAuthPanel(authBearer: draft.authBearer),
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
                    final next = Map<String, String>.from(draft.pathParams)
                      ..[e.key] = v;
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
        initialValue:
            selected.isEmpty && options.isNotEmpty ? options.first : selected,
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
                  Icon(
                    Icons.lock_outline,
                    size: 14,
                    color: AppColors.textSecondaryDark,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      'Authorization: Bearer ${_maskBearer(draft.authBearer)} '
                      '(locked — managed by Auth tab)',
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
                    child: Text(
                      e.key,
                      style: Theme.of(context).textTheme.labelLarge,
                    ),
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
                    onPressed:
                        widget.loading ? null : () => widget.onPickFile(e.key),
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
}
