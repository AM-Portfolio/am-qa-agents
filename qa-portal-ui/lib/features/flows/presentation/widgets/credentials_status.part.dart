part of 'credentials_manager.dart';

class _StatusChip extends StatelessWidget {
  const _StatusChip({
    required this.probing,
    required this.probe,
    required this.hasSecret,
  });

  final bool probing;
  final Map<String, dynamic>? probe;
  final bool hasSecret;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    if (probing) {
      return SizedBox(
        width: 16,
        height: 16,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          color: scheme.primary,
        ),
      );
    }
    if (probe != null) {
      final ok = probe!['ok'] == true;
      final status = '${probe!['status'] ?? (ok ? 'connected' : 'error')}';
      final color = ok ? Colors.green.shade600 : Colors.orange.shade700;
      final icon = ok ? Icons.check_circle : Icons.error_outline;
      return Tooltip(
        message: '${probe!['message'] ?? status}'
            '${probe!['latency_ms'] != null ? ' · ${probe!['latency_ms']}ms' : ''}',
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: color),
            const SizedBox(width: 4),
            Text(
              ok ? 'connected' : status,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ],
        ),
      );
    }
    if (hasSecret) {
      return Tooltip(
        message: 'Secret stored — tap refresh to test live',
        child: Icon(Icons.cloud_done_outlined, size: 16, color: scheme.outline),
      );
    }
    return Tooltip(
      message: 'No secret stored',
      child: Icon(Icons.cloud_off_outlined, size: 16, color: scheme.outline),
    );
  }
}

