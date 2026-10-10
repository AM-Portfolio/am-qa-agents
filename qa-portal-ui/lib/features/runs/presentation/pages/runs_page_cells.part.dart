part of 'runs_page.dart';

Widget _colHeader(BuildContext context, String label, {required int flex}) {
  return Expanded(
    flex: flex,
    child: Text(
      label,
      style: Theme.of(context).textTheme.labelSmall?.copyWith(
            fontWeight: FontWeight.w700,
          ),
    ),
  );
}


String _fmtStarted(String raw) {
  if (raw.isEmpty) return '—';
  final dt = DateTime.tryParse(raw);
  if (dt == null) return raw;
  final local = dt.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${local.year}-${two(local.month)}-${two(local.day)} '
      '${two(local.hour)}:${two(local.minute)}';
}

bool _isPlaywrightRun(Map<String, dynamic> r) {
  final tt = '${r['test_type'] ?? ''}'.toLowerCase();
  final runner = '${r['runner'] ?? ''}'.toLowerCase();
  return tt == 'playwright' ||
      runner.contains('asrax-release-ops') ||
      runner.contains('ui-test');
}

class _ApiCountsCell extends StatelessWidget {
  const _ApiCountsCell({
    required this.apiCount,
    required this.passN,
    required this.failN,
    this.stepsLabel = false,
  });

  final Object? apiCount;
  final Object? passN;
  final Object? failN;
  final bool stepsLabel;

  @override
  Widget build(BuildContext context) {
    final hasAny = apiCount != null || passN != null || failN != null;
    if (!hasAny) {
      return Text(
        stepsLabel ? '0 steps' : '—',
        style: Theme.of(context).textTheme.bodySmall,
      );
    }
    final total = apiCount ??
        ((passN is num ? passN as num : 0) + (failN is num ? failN as num : 0));
    final pass = passN ?? '—';
    final fail = failN ?? '—';
    final failNum = failN is num ? failN as num : null;
    return Text.rich(
      TextSpan(
        style: Theme.of(context).textTheme.bodySmall,
        children: [
          if (stepsLabel)
            TextSpan(
              text: 'Steps ',
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.55),
              ),
            ),
          TextSpan(
            text: '$total',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const TextSpan(text: ' · '),
          TextSpan(
            text: '$pass✓',
            style: const TextStyle(color: Colors.green, fontWeight: FontWeight.w600),
          ),
          const TextSpan(text: ' '),
          TextSpan(
            text: '$fail✗',
            style: TextStyle(
              color: (failNum != null && failNum > 0)
                  ? Theme.of(context).colorScheme.error
                  : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.55),
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    );
  }
}

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      'passed' || 'completed' => Colors.green,
      'failed' || 'error' => Theme.of(context).colorScheme.error,
      'running' || 'pending' => AppColors.primary,
      'cancelled' => Colors.orange,
      _ => Theme.of(context).colorScheme.outline,
    };
    return CircleAvatar(radius: 6, backgroundColor: color);
  }
}
