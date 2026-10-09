import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';

/// Narrow icon+label strip: Collections | Datasets.
class SpecsPrimaryRail extends StatelessWidget {
  const SpecsPrimaryRail({
    super.key,
    required this.state,
    required this.cubit,
    this.collapsed = false,
    this.onToggleCollapse,
  });

  final SpecsState state;
  final SpecsCubit cubit;
  final bool collapsed;
  final VoidCallback? onToggleCollapse;

  @override
  Widget build(BuildContext context) {
    final width = collapsed ? 48.0 : 80.0;
    final cs = Theme.of(context).colorScheme;
    return GlassCard(
      padding: EdgeInsets.zero,
      child: SizedBox(
        width: width,
        child: Column(
          children: [
            const SizedBox(height: 8),
            if (onToggleCollapse != null)
              IconButton(
                tooltip: collapsed ? 'Expand' : 'Collapse',
                icon: Icon(
                  collapsed ? Icons.chevron_right : Icons.chevron_left,
                  size: 18,
                ),
                onPressed: onToggleCollapse,
              ),
            const SizedBox(height: 4),
            _NavTile(
              icon: Icons.folder_outlined,
              label: 'Collections',
              selected: state.navMode == SpecsNavMode.collections,
              collapsed: collapsed,
              onTap: () => cubit.setNavMode(SpecsNavMode.collections),
            ),
            const SizedBox(height: 8),
            _NavTile(
              icon: Icons.storage_outlined,
              label: 'Datasets',
              selected: state.navMode == SpecsNavMode.datasets,
              collapsed: collapsed,
              onTap: () => cubit.setNavMode(SpecsNavMode.datasets),
            ),
            const Spacer(),
            Padding(
              padding: const EdgeInsets.all(6),
              child: Icon(
                Icons.api_outlined,
                size: 16,
                color: cs.onSurfaceVariant.withValues(alpha: 0.5),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavTile extends StatelessWidget {
  const _NavTile({
    required this.icon,
    required this.label,
    required this.selected,
    required this.collapsed,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final bool collapsed;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final fg = selected ? cs.primary : cs.onSurfaceVariant;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: Material(
        color: selected
            ? AppColors.primary.withValues(alpha: 0.14)
            : Colors.transparent,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: onTap,
          child: Padding(
            padding: EdgeInsets.symmetric(
              vertical: 10,
              horizontal: collapsed ? 0 : 4,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 22, color: fg),
                if (!collapsed) ...[
                  const SizedBox(height: 4),
                  Text(
                    label,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: fg,
                          fontWeight:
                              selected ? FontWeight.w700 : FontWeight.w500,
                          fontSize: 10,
                        ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
