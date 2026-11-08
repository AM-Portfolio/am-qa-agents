import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Pretty JSON/text with truncated preview + Copy all.
class JsonPreview extends StatelessWidget {
  const JsonPreview({
    super.key,
    required this.value,
    this.emptyLabel = 'No data',
    this.maxLines = 40,
  });

  final Object? value;
  final String emptyLabel;
  final int maxLines;

  String get fullText {
    if (value == null) return '';
    if (value is String) return value as String;
    try {
      return const JsonEncoder.withIndent('  ').convert(value);
    } catch (_) {
      return '$value';
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = fullText;
    if (text.isEmpty) {
      return Text(emptyLabel, style: Theme.of(context).textTheme.bodySmall);
    }
    final lines = const LineSplitter().convert(text);
    final truncated = lines.length > maxLines;
    final shown = truncated ? lines.take(maxLines).join('\n') : text;
    final more = truncated ? lines.length - maxLines : 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            const Spacer(),
            TextButton.icon(
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: text));
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Copied')),
                  );
                }
              },
              icon: const Icon(Icons.copy, size: 14),
              label: const Text('Copy all'),
            ),
          ],
        ),
        Expanded(
          child: SingleChildScrollView(
            child: SelectableText(
              shown,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
            ),
          ),
        ),
        if (truncated)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              '+$more more lines — use Copy all',
              style: Theme.of(context).textTheme.labelSmall,
            ),
          ),
      ],
    );
  }
}
