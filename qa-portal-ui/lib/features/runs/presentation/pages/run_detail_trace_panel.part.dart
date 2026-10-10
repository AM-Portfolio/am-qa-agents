part of 'run_detail_page.dart';

class _TraceDetailPanel extends StatelessWidget {
  const _TraceDetailPanel({
    required this.trace,
    required this.apiId,
    required this.onSavePayload,
    required this.absUrl,
  });

  final Map<String, dynamic> trace;
  final String? apiId;
  final Future<void> Function(String apiId) onSavePayload;
  final String Function(String) absUrl;

  bool get _isUiStep => '${trace['kind'] ?? ''}' == 'ui_step';

  Future<void> _copy(BuildContext context, String label, String text) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$label copied'), duration: const Duration(seconds: 1)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final method = (_nonEmpty(trace['method']) ?? 'GET').toUpperCase();
    final url = _traceUrl(trace);
    final endpoint = _endpointLabel(trace);
    final req = trace['request'] is Map
        ? Map<String, dynamic>.from(trace['request'] as Map)
        : <String, dynamic>{};
    final res = trace['response'] is Map
        ? Map<String, dynamic>.from(trace['response'] as Map)
        : <String, dynamic>{};
    final status = _traceStatus(trace);
    final ms = trace['timings'] is Map
        ? (trace['timings'] as Map)['duration_ms']
        : (trace['duration_ms'] ?? trace['latency_ms']);
    final structured = _hasStructuredTrace(trace) || !_isUiStep;
    final shotUrl = '${trace['screenshot_url'] ?? ''}';
    final reqBody = _prettyJson(req['body'] ?? (req.isEmpty ? null : req));
    final resBody = _prettyJson(res['body'] ?? (res.isEmpty ? null : res));
    final headersText = _prettyJson({
      'request': req['headers'] ?? {},
      'response': res['headers'] ?? {},
    });
    final curl = _isUiStep ? '' : _curlFromTrace(trace);
    final statusColor = _statusColor(context, status);
    final failed = _traceFailed(trace);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                (failed ? Theme.of(context).colorScheme.error : AppColors.primary)
                    .withValues(alpha: 0.08),
                Colors.transparent,
              ],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
            border: Border(
              bottom: BorderSide(
                color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.45),
              ),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 6,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.14),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      _isUiStep ? 'UI · $method' : method,
                      style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12),
                    ),
                  ),
                  if (status != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: statusColor.withValues(alpha: 0.14),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '$status',
                        style: TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: 12,
                          color: statusColor,
                        ),
                      ),
                    ),
                  if (ms != null)
                    Text(
                      '$ms ms',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                    ),
                  Text(
                    failed ? 'FAIL' : 'PASS',
                    style: TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 12,
                      color: failed
                          ? Theme.of(context).colorScheme.error
                          : Colors.green.shade700,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                endpoint,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              if (url.isNotEmpty && url != endpoint) ...[
                const SizedBox(height: 4),
                SelectableText(
                  url,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontFamily: 'Consolas',
                        height: 1.3,
                      ),
                ),
              ],
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  if (!_isUiStep)
                    FilledButton.tonalIcon(
                      onPressed: curl.isEmpty ? null : () => _copy(context, 'curl', curl),
                      icon: const Icon(Icons.terminal, size: 18),
                      label: const Text('Copy curl'),
                    ),
                  OutlinedButton.icon(
                    onPressed: () => _copy(context, 'Response', resBody),
                    icon: const Icon(Icons.copy_all, size: 18),
                    label: const Text('Copy response'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => _copy(context, 'Request', reqBody),
                    icon: const Icon(Icons.copy, size: 18),
                    label: const Text('Copy request'),
                  ),
                  if (!_isUiStep && apiId != null && apiId!.isNotEmpty)
                    OutlinedButton.icon(
                      onPressed: () => onSavePayload(apiId!),
                      icon: const Icon(Icons.save, size: 18),
                      label: const Text('Save payload'),
                    ),
                ],
              ),
            ],
          ),
        ),
        Expanded(
          child: structured
              ? DefaultTabController(
                  length: _isUiStep ? 4 : 5,
                  child: Column(
                    children: [
                      TabBar(
                        isScrollable: true,
                        tabs: _isUiStep
                            ? const [
                                Tab(text: 'Step'),
                                Tab(text: 'Result'),
                                Tab(text: 'Screenshot'),
                                Tab(text: 'Raw'),
                              ]
                            : const [
                                Tab(text: 'Request'),
                                Tab(text: 'Response'),
                                Tab(text: 'Headers'),
                                Tab(text: 'cURL'),
                                Tab(text: 'Raw'),
                              ],
                      ),
                      Expanded(
                        child: TabBarView(
                          children: _isUiStep
                              ? [
                                  _CodePane(text: reqBody, label: 'Step'),
                                  _CodePane(text: resBody, label: 'Result'),
                                  _ScreenshotPane(
                                    url: shotUrl.isEmpty ? null : absUrl(shotUrl),
                                  ),
                                  _CodePane(text: _prettyJson(trace), label: 'Raw'),
                                ]
                              : [
                                  _CodePane(text: reqBody, label: 'Request'),
                                  _CodePane(text: resBody, label: 'Response'),
                                  _CodePane(text: headersText, label: 'Headers'),
                                  _CodePane(text: curl, label: 'cURL', languageHint: 'bash'),
                                  _CodePane(text: _prettyJson(trace), label: 'Raw'),
                                ],
                        ),
                      ),
                    ],
                  ),
                )
              : _CodePane(text: _prettyJson(trace), label: 'Trace'),
        ),
      ],
    );
  }
}

class _ScreenshotPane extends StatelessWidget {
  const _ScreenshotPane({this.url});

  final String? url;

  @override
  Widget build(BuildContext context) {
    if (url == null || url!.isEmpty) {
      return Center(
        child: Text(
          'No screenshot for this step',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: () => launchUrl(Uri.parse(url!)),
              icon: const Icon(Icons.open_in_new, size: 16),
              label: const Text('Open'),
            ),
          ),
          Expanded(
            child: InteractiveViewer(
              minScale: 0.5,
              maxScale: 4,
              child: Image.network(
                url!,
                fit: BoxFit.contain,
                errorBuilder: (_, __, ___) => Center(
                  child: Text(
                    'Could not load screenshot',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
                loadingBuilder: (context, child, progress) {
                  if (progress == null) return child;
                  return const Center(child: CircularProgressIndicator(strokeWidth: 2));
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CodePane extends StatelessWidget {
  const _CodePane({
    required this.text,
    required this.label,
    this.languageHint,
  });

  final String text;
  final String label;
  final String? languageHint;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 8, 0),
          child: Row(
            children: [
              Text(
                label,
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              if (languageHint != null) ...[
                const SizedBox(width: 8),
                Chip(
                  label: Text(languageHint!),
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                ),
              ],
              const Spacer(),
              TextButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: text));
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('$label copied'),
                      duration: const Duration(seconds: 1),
                    ),
                  );
                },
                icon: const Icon(Icons.copy, size: 16),
                label: const Text('Copy'),
              ),
            ],
          ),
        ),
        Expanded(
          child: Container(
            margin: const EdgeInsets.fromLTRB(12, 4, 12, 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHighest.withValues(alpha: 0.55),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: scheme.outlineVariant.withValues(alpha: 0.45),
              ),
            ),
            child: SingleChildScrollView(
              child: SelectableText(
                text,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontFamily: 'Consolas',
                      height: 1.45,
                      fontSize: 12.5,
                    ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

