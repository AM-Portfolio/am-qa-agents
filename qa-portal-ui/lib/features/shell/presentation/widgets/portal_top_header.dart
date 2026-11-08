import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/config/connection_presets.dart';
import '../../../../core/config/portal_runtime.dart';
import '../../../../core/di/injection.dart';
import '../../../../core/router/app_router.dart';
import '../../../specs/data/specs_repository.dart';
import '../../data/workspace_store.dart';
import '../cubit/portal_notifications.dart';
import '../cubit/workspace_cubit.dart';
import 'environments_sheet.dart';
import 'portal_import_dialog.dart';

typedef PortalProfileOpener = Future<void> Function(BuildContext context);

/// Postman-inspired top chrome with AM styling (not a visual clone).
class PortalTopHeader extends StatefulWidget {
  const PortalTopHeader({
    super.key,
    required this.apiOk,
    this.apiMessage,
    this.onOpenProfile,
    this.onRefreshHealth,
    this.onClearCache,
  });

  final bool apiOk;
  final String? apiMessage;
  final PortalProfileOpener? onOpenProfile;
  final VoidCallback? onRefreshHealth;
  final VoidCallback? onClearCache;

  @override
  State<PortalTopHeader> createState() => _PortalTopHeaderState();
}

class _PortalTopHeaderState extends State<PortalTopHeader> {
  List<Map<String, dynamic>> _catalog = const [];
  bool _catalogLoaded = false;

  static const _navHints = <(String title, String route)>[
    ('Services', AppRoutes.services),
    ('Runs', AppRoutes.runs),
    ('Profiles', AppRoutes.profiles),
    ('OpenAPI', AppRoutes.specs),
    ('Datasets', AppRoutes.datasets),
    ('Flows', AppRoutes.flows),
    ('UI flows', AppRoutes.uiFlows),
  ];

  String _connectionLabel(PortalWorkspace? ws) {
    final base = ws?.resolvedApiBase(
          fallback: getIt.isRegistered<PortalRuntime>()
              ? getIt<PortalRuntime>().apiBase
              : ConnectionPreset.local.apiBase,
        ) ??
        (getIt.isRegistered<PortalRuntime>()
            ? getIt<PortalRuntime>().apiBase
            : ConnectionPreset.local.apiBase);
    final preset = ConnectionPreset.byId(ws?.connectionId) ??
        ConnectionPreset.byApiBase(base);
    return preset?.label ?? 'Custom';
  }

  @override
  void initState() {
    super.initState();
    _ensureCatalog();
  }

  Future<void> _ensureCatalog() async {
    if (_catalogLoaded) return;
    try {
      final listed = await getIt<SpecsRepository>().listServices();
      final services = [
        for (final id in listed.ids)
          {'id': id, 'label': listed.labels[id] ?? id},
      ];
      if (!mounted) return;
      setState(() {
        _catalog = services;
        _catalogLoaded = true;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _catalogLoaded = true);
    }
  }

  void _goBack(BuildContext context) {
    final router = GoRouter.of(context);
    if (router.canPop()) {
      router.pop();
    }
  }

  Future<void> _onSelectWorkspace(PortalWorkspace ws) async {
    await context.read<WorkspaceCubit>().select(ws.id);
    final svc = ws.defaultService;
    if (svc != null && svc.isNotEmpty) {
      context.go('${AppRoutes.specs}?spec=${Uri.encodeComponent(svc)}');
    } else {
      context.go(AppRoutes.services);
    }
  }

  Future<void> _createWorkspace() async {
    final nameCtrl = TextEditingController(text: 'New workspace');
    final envCtrl = TextEditingController(
      text: context.read<WorkspaceCubit>().state.active?.environment ?? 'dev',
    );
    final svcCtrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('New workspace'),
        content: SizedBox(
          width: 360,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameCtrl,
                decoration: const InputDecoration(
                  labelText: 'Name',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: envCtrl,
                decoration: const InputDecoration(
                  labelText: 'Environment',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: svcCtrl,
                decoration: const InputDecoration(
                  labelText: 'Default service (optional)',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    final ws = await context.read<WorkspaceCubit>().create(
          name: nameCtrl.text.trim().isEmpty
              ? 'Workspace'
              : nameCtrl.text.trim(),
          environment:
              envCtrl.text.trim().isEmpty ? 'dev' : envCtrl.text.trim(),
          defaultService:
              svcCtrl.text.trim().isEmpty ? null : svcCtrl.text.trim(),
        );
    await _onSelectWorkspace(ws);
  }

  void _showNotifications() {
    final cubit = context.read<PortalNotificationsCubit>();
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (ctx) {
        return BlocBuilder<PortalNotificationsCubit, PortalNotificationsState>(
          bloc: cubit,
          builder: (ctx, state) {
            if (state.items.isEmpty) {
              return const Padding(
                padding: EdgeInsets.all(24),
                child: Text('No recent notices'),
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
              itemCount: state.items.length + 1,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (ctx, i) {
                if (i == 0) {
                  return ListTile(
                    title: const Text('Notifications'),
                    trailing: TextButton(
                      onPressed: () {
                        cubit.clear();
                        Navigator.pop(ctx);
                      },
                      child: const Text('Clear'),
                    ),
                  );
                }
                final n = state.items[i - 1];
                return ListTile(
                  leading: Icon(
                    n.isError ? Icons.error_outline : Icons.check_circle_outline,
                    color: n.isError
                        ? Theme.of(ctx).colorScheme.error
                        : Theme.of(ctx).colorScheme.primary,
                  ),
                  title: Text(n.message),
                  subtitle: Text(n.at.toLocal().toString()),
                );
              },
            );
          },
        );
      },
    );
  }

  List<(String label, VoidCallback onTap)> _searchHits(String q) {
    final query = q.trim().toLowerCase();
    if (query.isEmpty) return const [];
    final out = <(String, VoidCallback)>[];
    for (final n in _navHints) {
      if (n.$1.toLowerCase().contains(query)) {
        out.add((n.$1, () => context.go(n.$2)));
      }
    }
    for (final s in _catalog) {
      final id = '${s['id'] ?? s['service'] ?? s['key'] ?? ''}';
      final label = '${s['label'] ?? id}';
      if (id.toLowerCase().contains(query) ||
          label.toLowerCase().contains(query)) {
        out.add((
          label.isEmpty ? id : label,
          () {
            context.read<WorkspaceCubit>().saveActive(defaultService: id);
            context.go('${AppRoutes.specs}?spec=${Uri.encodeComponent(id)}');
          }
        ));
      }
      if (out.length >= 12) break;
    }
    return out;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final canPop = GoRouter.of(context).canPop();

    return Material(
      color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.35),
      child: SizedBox(
        height: 48,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          child: Row(
            children: [
              IconButton(
                tooltip: 'Back',
                onPressed: canPop ? () => _goBack(context) : null,
                icon: const Icon(Icons.arrow_back),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                tooltip: 'Forward',
                onPressed: null,
                icon: const Icon(Icons.arrow_forward),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                tooltip: 'Home',
                onPressed: () => context.go(AppRoutes.services),
                icon: const Icon(Icons.home_outlined),
                visualDensity: VisualDensity.compact,
              ),
              const SizedBox(width: 4),
              BlocBuilder<WorkspaceCubit, WorkspaceCubitState>(
                builder: (context, ws) {
                  final active = ws.active;
                  return PopupMenuButton<String>(
                    tooltip: 'Workspace',
                    onSelected: (id) async {
                      if (id == '__new__') {
                        await _createWorkspace();
                        return;
                      }
                      final match = ws.workspaces
                          .cast<PortalWorkspace?>()
                          .firstWhere(
                            (w) => w?.id == id,
                            orElse: () => null,
                          );
                      if (match != null) await _onSelectWorkspace(match);
                    },
                    itemBuilder: (ctx) => [
                      for (final w in ws.workspaces)
                        PopupMenuItem(
                          value: w.id,
                          child: ListTile(
                            dense: true,
                            contentPadding: EdgeInsets.zero,
                            leading: Icon(
                              w.id == active?.id
                                  ? Icons.check_circle
                                  : Icons.circle_outlined,
                              size: 18,
                            ),
                            title: Text(w.name),
                            subtitle: Text(
                              [
                                _connectionLabel(w),
                                w.environment,
                                if (w.defaultService != null) w.defaultService!,
                              ].join(' · '),
                            ),
                          ),
                        ),
                      const PopupMenuDivider(),
                      const PopupMenuItem(
                        value: '__new__',
                        child: ListTile(
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          leading: Icon(Icons.add, size: 18),
                          title: Text('New workspace'),
                        ),
                      ),
                    ],
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.workspaces_outlined,
                            size: 18,
                            color: theme.colorScheme.primary,
                          ),
                          const SizedBox(width: 6),
                          ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 180),
                            child: Text(
                              active?.name ?? 'Workspace',
                              overflow: TextOverflow.ellipsis,
                              style: theme.textTheme.labelLarge?.copyWith(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          const Icon(Icons.expand_more, size: 18),
                        ],
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(width: 8),
              BlocBuilder<WorkspaceCubit, WorkspaceCubitState>(
                builder: (context, ws) {
                  final label = _connectionLabel(ws.active);
                  final env = ws.active?.environment ?? 'dev';
                  return ActionChip(
                    avatar: Icon(
                      widget.apiOk ? Icons.cloud_done_outlined : Icons.cloud_off,
                      size: 16,
                      color: widget.apiOk
                          ? theme.colorScheme.primary
                          : theme.colorScheme.error,
                    ),
                    label: Text('$label · $env'),
                    onPressed: () => showEnvironmentsSheet(
                      context,
                      onSaved: widget.onRefreshHealth,
                    ),
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  );
                },
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Autocomplete<(String, VoidCallback)>(
                  displayStringForOption: (o) => o.$1,
                  optionsBuilder: (text) => _searchHits(text.text),
                  onSelected: (o) => o.$2(),
                  fieldViewBuilder:
                      (context, controller, focusNode, onSubmit) {
                    return TextField(
                      controller: controller,
                      focusNode: focusNode,
                      onSubmitted: (_) => onSubmit(),
                      decoration: InputDecoration(
                        isDense: true,
                        hintText: 'Search services & pages',
                        prefixIcon: const Icon(Icons.search, size: 18),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(20),
                        ),
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                      ),
                      style: theme.textTheme.bodyMedium,
                    );
                  },
                  optionsViewBuilder: (context, onSelected, options) {
                    return Align(
                      alignment: Alignment.topLeft,
                      child: Material(
                        elevation: 4,
                        borderRadius: BorderRadius.circular(8),
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(
                            maxHeight: 280,
                            maxWidth: 420,
                          ),
                          child: ListView.builder(
                            padding: EdgeInsets.zero,
                            shrinkWrap: true,
                            itemCount: options.length,
                            itemBuilder: (ctx, i) {
                              final o = options.elementAt(i);
                              return ListTile(
                                dense: true,
                                title: Text(o.$1),
                                onTap: () => onSelected(o),
                              );
                            },
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(width: 8),
              TextButton.icon(
                onPressed: () => showPortalImportDialog(context),
                icon: const Icon(Icons.upload_file_outlined, size: 18),
                label: const Text('Import'),
              ),
              PopupMenuButton<String>(
                tooltip: 'API / cache',
                onSelected: (v) {
                  if (v == 'refresh') widget.onRefreshHealth?.call();
                  if (v == 'clear') widget.onClearCache?.call();
                },
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'refresh',
                    child: Text(widget.apiOk ? 'Refresh health' : 'Retry health'),
                  ),
                  const PopupMenuItem(
                    value: 'clear',
                    child: Text('Clear cache'),
                  ),
                ],
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 6),
                  child: Icon(
                    widget.apiOk ? Icons.sync : Icons.sync_problem,
                    color: widget.apiOk
                        ? theme.colorScheme.primary
                        : theme.colorScheme.error,
                  ),
                ),
              ),
              BlocBuilder<PortalNotificationsCubit, PortalNotificationsState>(
                builder: (context, notes) {
                  return IconButton(
                    tooltip: 'Notifications',
                    onPressed: _showNotifications,
                    icon: Badge(
                      isLabelVisible: notes.unread > 0,
                      label: Text('${notes.unread}'),
                      child: const Icon(Icons.notifications_outlined),
                    ),
                    visualDensity: VisualDensity.compact,
                  );
                },
              ),
              IconButton(
                tooltip: 'Environments',
                onPressed: () => showEnvironmentsSheet(
                  context,
                  onSaved: widget.onRefreshHealth,
                ),
                icon: const Icon(Icons.tune),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                tooltip: 'Operator profile',
                onPressed: widget.onOpenProfile == null
                    ? null
                    : () => widget.onOpenProfile!(context),
                icon: const Icon(Icons.settings_outlined),
                visualDensity: VisualDensity.compact,
              ),
              if (widget.apiMessage != null && widget.apiMessage!.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(left: 4, right: 8),
                  child: Text(
                    widget.apiMessage!,
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.error,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
