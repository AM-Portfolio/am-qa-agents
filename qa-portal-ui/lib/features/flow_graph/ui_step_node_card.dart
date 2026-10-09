import 'package:flutter/material.dart';

import 'ui_step_node_data.dart';

/// Summary-only card for UI / Playwright steps (full detail stays on Run page).
class UiStepNodeCard extends StatelessWidget {
  const UiStepNodeCard({
    super.key,
    required this.data,
    this.onTrigger,
    this.onAdd,
    this.onDelete,
    this.onOpenInRun,
    this.readOnly = false,
  });

  final UiStepNodeData data;
  final VoidCallback? onTrigger;
  final VoidCallback? onAdd;
  final VoidCallback? onDelete;
  final VoidCallback? onOpenInRun;
  final bool readOnly;

  Color _border(BuildContext context) {
    switch ((data.status ?? '').toLowerCase()) {
      case 'ok':
      case 'pass':
      case 'passed':
      case 'completed':
        return const Color(0xFF2E7D32);
      case 'fail':
      case 'failed':
      case 'error':
        return const Color(0xFFC62828);
      case 'running':
        return const Color(0xFF1565C0);
      case 'skipped':
      case 'warn':
        return const Color(0xFF757575);
      default:
        return data.isManualTrigger
            ? const Color(0xFF7B1FA2)
            : (data.selected
                ? Theme.of(context).colorScheme.primary
                : Theme.of(context).colorScheme.outlineVariant);
    }
  }

  String _statusLabel() {
    final s = (data.status ?? '').toLowerCase();
    if (s == 'ok' || s == 'pass' || s == 'passed' || s == 'completed') {
      return 'PASS';
    }
    if (s == 'fail' || s == 'failed' || s == 'error') return 'FAIL';
    if (s == 'running') return 'RUN';
    if (s == 'skipped' || s == 'warn') return 'SKIP';
    return '';
  }

  @override
  Widget build(BuildContext context) {
    if (data.isManualTrigger) {
      return SizedBox(
        width: 140,
        child: Card(
          elevation: data.selected ? 3 : 1,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: BorderSide(color: _border(context), width: 2),
          ),
          child: InkWell(
            onTap: onTrigger,
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.play_circle_fill, color: _border(context), size: 28),
                  const SizedBox(height: 6),
                  Text(
                    data.label,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    final statusLabel = _statusLabel();
    final border = _border(context);
    return SizedBox(
      width: 220,
      child: Card(
        elevation: data.selected ? 3 : 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: BorderSide(
            color: border,
            width: data.selected || data.status != null ? 2 : 1,
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: Theme.of(context)
                          .colorScheme
                          .primary
                          .withValues(alpha: 0.14),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      data.method,
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  if (data.isVerification) ...[
                    const SizedBox(width: 6),
                    Text(
                      'verify',
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                  ],
                  const Spacer(),
                  if (statusLabel.isNotEmpty)
                    Text(
                      statusLabel,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        color: border,
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                data.label,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12),
              ),
              if (data.durationMs != null) ...[
                const SizedBox(height: 4),
                Text(
                  '${data.durationMs!.toStringAsFixed(data.durationMs! >= 100 ? 0 : 1)} ms',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ],
              if (data.requestPeek != null && data.requestPeek!.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  data.requestPeek!,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context)
                            .colorScheme
                            .onSurface
                            .withValues(alpha: 0.55),
                      ),
                ),
              ],
              if (data.responsePeek != null &&
                  data.responsePeek!.isNotEmpty) ...[
                Text(
                  data.responsePeek!,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context)
                            .colorScheme
                            .onSurface
                            .withValues(alpha: 0.55),
                      ),
                ),
              ],
              if (data.screenshotUrl != null &&
                  data.screenshotUrl!.isNotEmpty) ...[
                const SizedBox(height: 6),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: Image.network(
                    data.screenshotUrl!,
                    height: 56,
                    width: double.infinity,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => Container(
                      height: 40,
                      alignment: Alignment.center,
                      color: Theme.of(context)
                          .colorScheme
                          .surfaceContainerHighest,
                      child: const Text('No preview', style: TextStyle(fontSize: 10)),
                    ),
                  ),
                ),
              ],
              if (!readOnly || onOpenInRun != null) ...[
                const SizedBox(height: 6),
                Wrap(
                  spacing: 2,
                  children: [
                    if (onOpenInRun != null)
                      IconButton(
                        tooltip: 'Open in Run',
                        iconSize: 18,
                        visualDensity: VisualDensity.compact,
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(
                          minWidth: 28,
                          minHeight: 28,
                        ),
                        onPressed: onOpenInRun,
                        icon: const Icon(Icons.open_in_new, size: 18),
                      ),
                    if (!readOnly) ...[
                      IconButton(
                        tooltip: 'Add step after',
                        iconSize: 18,
                        visualDensity: VisualDensity.compact,
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(
                          minWidth: 28,
                          minHeight: 28,
                        ),
                        onPressed: onAdd,
                        icon: Icon(
                          Icons.add_circle_outline,
                          size: 18,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                      ),
                      IconButton(
                        tooltip: 'Delete step',
                        iconSize: 18,
                        visualDensity: VisualDensity.compact,
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(
                          minWidth: 28,
                          minHeight: 28,
                        ),
                        onPressed: onDelete,
                        icon: Icon(
                          Icons.delete_outline,
                          size: 18,
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
