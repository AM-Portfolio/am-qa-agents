import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';
import '../cubit/specs_state.dart';

/// Narrow icon+label strip: Test | Swagger | MCP / AI | SDK | Use cases.
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

  void _selectTab(SpecsWorkspaceTab tab) {
    if (state.navMode != SpecsNavMode.collections) {
      cubit.setNavMode(SpecsNavMode.collections);
    }
    cubit.setWorkspaceTab(tab);
  }

  @override
  Widget build(BuildContext context) {
    final width = collapsed ? 48.0 : 80.0;
    final cs = Theme.of(context).colorScheme;
    final tab = state.workspaceTab;
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
              icon: Icons.play_arrow_outlined,
              label: 'Test',
              selected: tab == SpecsWorkspaceTab.test,
              collapsed: collapsed,
              onTap: () => _selectTab(SpecsWorkspaceTab.test),
            ),
            const SizedBox(height: 6),
            _NavTile(
              icon: Icons.description_outlined,
              label: 'Swagger',
              selected: tab == SpecsWorkspaceTab.swagger,
              collapsed: collapsed,
              onTap: () => _selectTab(SpecsWorkspaceTab.swagger),
            ),
            const SizedBox(height: 6),
            _NavTile(
              icon: Icons.smart_toy_outlined,
              label: 'MCP / AI',
              selected: tab == SpecsWorkspaceTab.mcp,
              collapsed: collapsed,
              onTap: () => _selectTab(SpecsWorkspaceTab.mcp),
            ),
            const SizedBox(height: 6),
            _NavTile(
              icon: Icons.code_outlined,
              label: 'SDK',
              selected: tab == SpecsWorkspaceTab.sdk,
              collapsed: collapsed,
              onTap: () => _selectTab(SpecsWorkspaceTab.sdk),
            ),
            const SizedBox(height: 6),
            _NavTile(
              icon: Icons.checklist_outlined,
              label: 'Use cases',
              selected: tab == SpecsWorkspaceTab.usecases,
              collapsed: collapsed,
              onTap: () => _selectTab(SpecsWorkspaceTab.usecases),
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
