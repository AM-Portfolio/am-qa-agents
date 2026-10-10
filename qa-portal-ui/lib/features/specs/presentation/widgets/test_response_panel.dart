import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import '../../domain/try_draft.dart';
import 'kv_editor.dart';

/// Response pane for [TestWorkspace].
class TestResponsePanel extends StatefulWidget {
  const TestResponsePanel({
    super.key,
    required this.tryResult,
    this.tryStatusCode,
    this.tryDurationMs,
  });

  final String? tryResult;
  final int? tryStatusCode;
  final int? tryDurationMs;

  @override
  State<TestResponsePanel> createState() => _TestResponsePanelState();
}

class _TestResponsePanelState extends State<TestResponsePanel> {
  String? _display;

  @override
  void initState() {
    super.initState();
    _display = widget.tryResult;
  }

  @override
  void didUpdateWidget(covariant TestResponsePanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.tryResult != widget.tryResult) {
      _display = widget.tryResult;
    }
  }

  void _formatInPlace() {
    final raw = _display ?? widget.tryResult;
    if (raw == null || raw.trim().isEmpty) return;
    try {
      final pretty = formatJsonBody(raw);
      if (pretty != null) setState(() => _display = pretty);
    } catch (_) {
      // leave as-is when not JSON
    }
  }

  @override
  Widget build(BuildContext context) {
    final code = widget.tryStatusCode;
    final sc = statusColor(code, context);
    final duration = widget.tryDurationMs;
    final text = _display ?? widget.tryResult ?? 'Send to see result.';
    final mono = Theme.of(context).textTheme.bodySmall?.copyWith(
          fontFamily: 'monospace',
          fontFamilyFallback: const ['Courier New', 'monospace'],
        );
    final canFormat = (widget.tryResult != null && widget.tryResult!.trim().isNotEmpty);

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
                  'Response',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                if (code != null) ...[
                  const SizedBox(width: 10),
                  Text(
                    'HTTP $code',
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                          color: sc,
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ],
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
                TextButton(
                  onPressed: canFormat ? _formatInPlace : null,
                  child: const Text('Format'),
                ),
              ],
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: SingleChildScrollView(
                child: SelectableText(text, style: mono),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
