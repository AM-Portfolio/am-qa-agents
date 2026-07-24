import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

/// Editable key/value table for headers, query params, etc.
class KvEditor extends StatelessWidget {
  const KvEditor({
    super.key,
    required this.entries,
    required this.onChanged,
    this.onRemove,
    this.onAdd,
    this.keyHint = 'Key',
    this.valueHint = 'Value',
    this.lockedKeys = const {},
  });

  final Map<String, String> entries;
  final void Function(String key, String value) onChanged;
  final void Function(String key)? onRemove;
  final VoidCallback? onAdd;
  final String keyHint;
  final String valueHint;
  final Set<String> lockedKeys;

  @override
  Widget build(BuildContext context) {
    final keys = entries.keys.toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final k in keys)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(
              children: [
                Expanded(
                  flex: 2,
                  child: TextFormField(
                    key: ValueKey('k-$k'),
                    initialValue: k,
                    enabled: !lockedKeys.contains(k),
                    decoration: InputDecoration(
                      labelText: keyHint,
                      isDense: true,
                      border: const OutlineInputBorder(),
                    ),
                    onChanged: (nk) {
                      if (nk == k || nk.isEmpty) return;
                      final v = entries[k] ?? '';
                      onRemove?.call(k);
                      onChanged(nk, v);
                    },
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  flex: 3,
                  child: TextFormField(
                    key: ValueKey('v-$k-${entries[k]}'),
                    initialValue: entries[k],
                    enabled: !lockedKeys.contains(k),
                    decoration: InputDecoration(
                      labelText: valueHint,
                      isDense: true,
                      border: const OutlineInputBorder(),
                      filled: lockedKeys.contains(k),
                    ),
                    onChanged: (v) => onChanged(k, v),
                  ),
                ),
                if (onRemove != null && !lockedKeys.contains(k))
                  IconButton(
                    tooltip: 'Remove',
                    onPressed: () => onRemove!(k),
                    icon: const Icon(Icons.close, size: 18),
                  ),
              ],
            ),
          ),
        if (onAdd != null)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: onAdd,
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Add'),
              style: TextButton.styleFrom(foregroundColor: AppColors.primary),
            ),
          ),
      ],
    );
  }
}

Color methodColor(String method) {
  switch (method.toUpperCase()) {
    case 'GET':
      return const Color(0xFF22C55E);
    case 'POST':
      return AppColors.primary;
    case 'PUT':
      return const Color(0xFFF59E0B);
    case 'PATCH':
      return const Color(0xFF06B6D4);
    case 'DELETE':
      return const Color(0xFFEF4444);
    default:
      return AppColors.textSecondaryDark;
  }
}

Color statusColor(int? code, BuildContext context) {
  if (code == null) return Theme.of(context).colorScheme.outline;
  if (code >= 200 && code < 300) return const Color(0xFF22C55E);
  if (code >= 400 && code < 500) return const Color(0xFFF59E0B);
  if (code >= 500) return const Color(0xFFEF4444);
  return AppColors.primary;
}
