import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import 'kv_editor.dart';

/// Response pane for [TestWorkspace].
class TestResponsePanel extends StatelessWidget {
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
  Widget build(BuildContext context) {
    final code = tryStatusCode;
    final sc = statusColor(code, context);
    final duration = tryDurationMs;
    final text = tryResult ?? 'Send or Mock 1× to see result.';
    final mono = Theme.of(context).textTheme.bodySmall?.copyWith(
          fontFamily: 'monospace',
          fontFamilyFallback: const ['Courier New', 'monospace'],
        );

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
                child: SelectableText(text, style: mono),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
