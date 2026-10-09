import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

/// Trace id + Grafana Explore / platform logs attach block.
class ObservabilityAttach extends StatefulWidget {
  const ObservabilityAttach({
    super.key,
    this.traceId,
    this.correlationId,
    this.observabilityResources,
    this.loadLogs,
    this.compact = false,
  });

  final String? traceId;
  final String? correlationId;
  final Map<String, dynamic>? observabilityResources;
  final Future<Map<String, dynamic>> Function()? loadLogs;
  final bool compact;

  @override
  State<ObservabilityAttach> createState() => _ObservabilityAttachState();
}

class _ObservabilityAttachState extends State<ObservabilityAttach> {
  bool _loadingLogs = false;
  Map<String, dynamic>? _logs;
  String? _logsError;
  bool _expanded = false;

  String get _trace =>
      (widget.traceId ?? widget.observabilityResources?['trace_id'] ?? '')
          .toString()
          .trim();

  String get _corr =>
      (widget.correlationId ??
              widget.observabilityResources?['correlation_id'] ??
              '')
          .toString()
          .trim();

  Map<String, dynamic> get _obs =>
      widget.observabilityResources is Map
          ? Map<String, dynamic>.from(widget.observabilityResources!)
          : const {};

  Future<void> _fetchLogs() async {
    if (widget.loadLogs == null) return;
    setState(() {
      _loadingLogs = true;
      _logsError = null;
      _expanded = true;
    });
    try {
      final out = await widget.loadLogs!();
      if (!mounted) return;
      setState(() {
        _logs = out;
        _loadingLogs = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _logsError = e.toString();
        _loadingLogs = false;
      });
    }
  }

  Future<void> _open(String? url) async {
    final u = (url ?? '').trim();
    if (u.isEmpty) return;
    await launchUrl(Uri.parse(u));
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final connected = _obs['connected'] is Map
        ? Map<String, dynamic>.from(_obs['connected'] as Map)
        : const <String, dynamic>{};
    final grafanaConnected = connected['grafana'] == true;
    final dash = '${_obs['grafana_dashboard_url'] ?? ''}';
    final loki = '${_obs['grafana_loki_explore_url'] ?? ''}';
    final tempo = '${_obs['grafana_tempo_explore_url'] ?? ''}';
    final prom = '${_obs['prometheus_explore_url'] ?? ''}';

    if (_trace.isEmpty &&
        _corr.isEmpty &&
        dash.isEmpty &&
        loki.isEmpty &&
        tempo.isEmpty) {
      return const SizedBox.shrink();
    }

    final lines = <Widget>[
      Wrap(
        spacing: 8,
        runSpacing: 6,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          if (_trace.isNotEmpty)
            _ChipLink(
              label: 'trace ${_short(_trace)}',
              icon: Icons.hub_outlined,
              onCopy: () => _copy(context, _trace, 'Trace id copied'),
            ),
          if (_corr.isNotEmpty && _corr != _trace)
            _ChipLink(
              label: 'corr ${_short(_corr)}',
              icon: Icons.link,
              onCopy: () => _copy(context, _corr, 'Correlation id copied'),
            ),
          if (dash.isNotEmpty)
            OutlinedButton.icon(
              onPressed: () => _open(dash),
              icon: const Icon(Icons.insights, size: 16),
              label: const Text('Dashboard'),
            ),
          if (loki.isNotEmpty)
            OutlinedButton.icon(
              onPressed: () => _open(loki),
              icon: const Icon(Icons.receipt_long, size: 16),
              label: const Text('Loki'),
            ),
          if (tempo.isNotEmpty)
            OutlinedButton.icon(
              onPressed: () => _open(tempo),
              icon: const Icon(Icons.timeline, size: 16),
              label: const Text('Tempo'),
            ),
          if (prom.isNotEmpty)
            OutlinedButton.icon(
              onPressed: () => _open(prom),
              icon: const Icon(Icons.speed, size: 16),
              label: const Text('Prom'),
            ),
          if (widget.loadLogs != null)
            FilledButton.tonalIcon(
              onPressed: _loadingLogs ? null : _fetchLogs,
              icon: _loadingLogs
                  ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.terminal, size: 16),
              label: Text(widget.compact ? 'Logs' : 'Platform logs'),
            ),
          if (!grafanaConnected)
            Text(
              'Connect Grafana for Explore links',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: scheme.outline,
                  ),
            ),
        ],
      ),
    ];

    if (_expanded || _logs != null || _logsError != null) {
      lines.add(const SizedBox(height: 8));
      lines.add(_LogsPane(logs: _logs, error: _logsError));
    }

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: EdgeInsets.all(widget.compact ? 8 : 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Observability',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: 6),
            ...lines,
          ],
        ),
      ),
    );
  }

  String _short(String s) =>
      s.length <= 14 ? s : '${s.substring(0, 6)}…${s.substring(s.length - 4)}';

  Future<void> _copy(BuildContext context, String text, String msg) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), duration: const Duration(seconds: 1)),
    );
  }
}

class _ChipLink extends StatelessWidget {
  const _ChipLink({
    required this.label,
    required this.icon,
    required this.onCopy,
  });

  final String label;
  final IconData icon;
  final VoidCallback onCopy;

  @override
  Widget build(BuildContext context) {
    return ActionChip(
      avatar: Icon(icon, size: 16),
      label: Text(label, style: const TextStyle(fontFamily: 'monospace')),
      onPressed: onCopy,
    );
  }
}

class _LogsPane extends StatelessWidget {
  const _LogsPane({this.logs, this.error});

  final Map<String, dynamic>? logs;
  final String? error;

  @override
  Widget build(BuildContext context) {
    if (error != null) {
      return Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error));
    }
    if (logs == null) {
      return const SizedBox.shrink();
    }
    final available = logs!['available'] == true;
    if (!available) {
      return Text(
        'Platform logs unavailable: ${logs!['reason'] ?? 'unknown'}',
        style: Theme.of(context).textTheme.bodySmall,
      );
    }
    final raw = logs!['lines'];
    final lines = raw is List ? raw : const [];
    if (lines.isEmpty) {
      return Text(
        'No Loki lines for this trace yet',
        style: Theme.of(context).textTheme.bodySmall,
      );
    }
    return ConstrainedBox(
      constraints: const BoxConstraints(maxHeight: 220),
      child: ListView.builder(
        shrinkWrap: true,
        itemCount: lines.length.clamp(0, 80),
        itemBuilder: (_, i) {
          final row = lines[i];
          final msg = row is Map
              ? '${row['message'] ?? row}'
              : '$row';
          final ts = row is Map ? '${row['ts'] ?? ''}' : '';
          return Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: SelectableText(
              ts.isEmpty ? msg : '$ts  $msg',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    fontFamily: 'monospace',
                    fontSize: 11,
                  ),
            ),
          );
        },
      ),
    );
  }
}
