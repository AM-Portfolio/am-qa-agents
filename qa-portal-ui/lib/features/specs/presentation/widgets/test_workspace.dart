import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import '../../domain/try_draft.dart';
import 'kv_editor.dart';
import 'test_request_panel.dart';
import 'test_response_panel.dart';

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
  static const _responseDefaultFraction = 0.4;
  static const _responseMin = 160.0;
  /// Inspector detail panes are often ~500–700px; keep side-by-side + drag usable.
  static const _sideBySideMin = 420.0;

  /// Absolute response pane width; null until first side-by-side layout.
  double? _responseWidth;

  TryDraft get draft => widget.draft;

  void _emit(TryDraft next) => widget.onDraftChanged(next);

  TextStyle? get _mono => Theme.of(context).textTheme.bodySmall?.copyWith(
        fontFamily: 'monospace',
        fontFamilyFallback: const ['Courier New', 'monospace'],
      );

  String _requestUrl() {
    var path = draft.resolvedPath.trim();
    if (path.isEmpty) path = '/';
    if (!path.startsWith('/')) path = '/$path';
    final q = draft.queryParams.entries
        .where((e) => e.value.isNotEmpty)
        .map(
          (e) =>
              '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}',
        )
        .join('&');
    final base = (widget.targetUrl ?? '').trim();
    final joined = base.isEmpty ? path : joinBasePath(base, path);
    return q.isEmpty ? joined : '$joined?$q';
  }

  @override
  Widget build(BuildContext context) {
    final saveLabel = widget.selectedPayloadVersion == null
        ? 'Save set'
        : 'Save to v${widget.selectedPayloadVersion}';
    final requestUrl = _requestUrl();

    return Padding(
      padding: const EdgeInsets.fromLTRB(6, 4, 6, 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildTopBar(context),
          const SizedBox(height: 4),
          SelectableText(
            requestUrl,
            maxLines: 1,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  fontFamily: 'monospace',
                  color: AppColors.textSecondaryDark,
                  fontSize: 11,
                ),
          ),
          const SizedBox(height: 4),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final sideBySide = constraints.maxWidth >= _sideBySideMin;
                final editor = TestRequestPanel(
                  draft: draft,
                  loading: widget.loading,
                  paramEnums: widget.paramEnums,
                  onDraftChanged: widget.onDraftChanged,
                  onPickFile: widget.onPickFile,
                  onRemoveFile: widget.onRemoveFile,
                  onFormat: widget.onFormat,
                );
                final response = TestResponsePanel(
                  tryResult: widget.tryResult,
                  tryStatusCode: widget.tryStatusCode,
                  tryDurationMs: widget.tryDurationMs,
                );
                if (sideBySide) {
                  final reqMin = 200.0;
                  final maxResp = (constraints.maxWidth - reqMin - 10)
                      .clamp(_responseMin, constraints.maxWidth * 0.7);
                  final defaultW =
                      (constraints.maxWidth * _responseDefaultFraction)
                          .clamp(_responseMin, maxResp);
                  final respW =
                      (_responseWidth ?? defaultW).clamp(_responseMin, maxResp);
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Expanded(child: editor),
                      MouseRegion(
                        cursor: SystemMouseCursors.resizeColumn,
                        child: GestureDetector(
                          behavior: HitTestBehavior.opaque,
                          onHorizontalDragUpdate: (d) {
                            setState(() {
                              _responseWidth = (respW - d.delta.dx)
                                  .clamp(_responseMin, maxResp);
                            });
                          },
                          onDoubleTap: () =>
                              setState(() => _responseWidth = defaultW),
                          child: SizedBox(
                            width: 10,
                            child: Center(
                              child: Container(
                                width: 3,
                                height: 48,
                                decoration: BoxDecoration(
                                  color: Theme.of(context)
                                      .dividerColor
                                      .withValues(alpha: 0.9),
                                  borderRadius: BorderRadius.circular(2),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                      SizedBox(width: respW, child: response),
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
                onPressed:
                    widget.tryResult == null ? null : widget.onCopyResponse,
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
                    width: 96,
                    child: DropdownButtonFormField<String>(
                      key: ValueKey('method-$method'),
                      isDense: true,
                      isExpanded: true,
                      initialValue: _methods.contains(method) ? method : 'GET',
                      decoration: InputDecoration(
                        isDense: true,
                        border: OutlineInputBorder(
                          borderSide: BorderSide(color: color, width: 1.5),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderSide: BorderSide(color: color, width: 1.5),
                        ),
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 8,
                        ),
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
                    width: (constraints.maxWidth - 200).clamp(160.0, 900.0),
                    child: TextFormField(
                      key: ValueKey('path-${draft.path}'),
                      initialValue: draft.path,
                      style: _mono,
                      decoration: const InputDecoration(
                        labelText: 'Path',
                        isDense: true,
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 10,
                        ),
                      ),
                      onChanged: (v) {
                        final params = pathParamsFromTemplate(v);
                        final merged = <String, String>{
                          for (final k in params.keys)
                            k: draft.pathParams[k] ?? '',
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
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
