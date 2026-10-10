import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

/// Auth tab for [TestWorkspace] — shows masked bearer / SPT try-token note.
class TestAuthPanel extends StatelessWidget {
  const TestAuthPanel({super.key, required this.authBearer});

  final String? authBearer;

  String _maskBearer(String? token) {
    if (token == null || token.isEmpty) return '(none)';
    if (token.length <= 10) return '••••••••';
    return '${token.substring(0, 4)}…${token.substring(token.length - 4)}';
  }

  @override
  Widget build(BuildContext context) {
    final mono = Theme.of(context).textTheme.bodySmall?.copyWith(
          fontFamily: 'monospace',
          fontFamilyFallback: const ['Courier New', 'monospace'],
        );
    return SingleChildScrollView(
      padding: const EdgeInsets.only(top: 8, right: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Bearer token', style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 6),
          SelectableText(_maskBearer(authBearer), style: mono),
          const SizedBox(height: 10),
          Text(
            'SPT try-token is used for authenticated Try / Mock requests. '
            'The portal attaches the platform try-token when you Send.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppColors.textSecondaryDark,
                ),
          ),
        ],
      ),
    );
  }
}
