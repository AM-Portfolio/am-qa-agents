import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/api/friendly_api_error.dart';
import '../../../../core/di/injection.dart';
import '../../../../core/router/app_router.dart';
import '../../../shell/presentation/widgets/environments_sheet.dart';
import '../../../specs/data/specs_repository.dart';
import '../cubit/datasets_cubit.dart';

/// Fleet inventory of hoist / payload-set version records.
class DatasetsPage extends StatelessWidget {
  const DatasetsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => DatasetsCubit(getIt<SpecsRepository>())..load(),
      child: const _DatasetsView(),
    );
  }
}

class _DatasetsView extends StatelessWidget {
  const _DatasetsView();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return BlocConsumer<DatasetsCubit, DatasetsState>(
      listenWhen: (p, c) => p.message != c.message && c.message != null,
      listener: (context, state) {
        final msg = state.message;
        if (msg == null) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
      },
      builder: (context, state) {
        final cubit = context.read<DatasetsCubit>();
        final rows = state.visible;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Row(
                children: [
                  Text('Datasets', style: theme.textTheme.titleLarge),
                  const SizedBox(width: 12),
                  Text(
                    'Each service can keep many payload-set versions',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const Spacer(),
                  OutlinedButton.icon(
                    onPressed: () => showEnvironmentsSheet(context),
                    icon: const Icon(Icons.tune, size: 18),
                    label: const Text('Environments'),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    tooltip: 'Refresh',
                    onPressed: state.loading ? null : cubit.load,
                    icon: state.loading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.refresh),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  SizedBox(
                    width: 280,
                    child: TextField(
                      decoration: const InputDecoration(
                        hintText: 'Filter services',
                        prefixIcon: Icon(Icons.search, size: 20),
                        isDense: true,
                        border: OutlineInputBorder(),
                      ),
                      onChanged: cubit.setFilter,
                    ),
                  ),
                  const SizedBox(width: 12),
                  FilterChip(
                    label: const Text('Active only'),
                    selected: state.activeOnly,
                    onSelected: cubit.setActiveOnly,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  SizedBox(
                    width: 220,
                    child: Text('Service', style: theme.textTheme.labelMedium),
                  ),
                  SizedBox(
                    width: 88,
                    child: Text('Active', style: theme.textTheme.labelMedium),
                  ),
                  Expanded(
                    child: Text(
                      'Versions (many per service)',
                      style: theme.textTheme.labelMedium,
                    ),
                  ),
                  const SizedBox(width: 140),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: state.loading && rows.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : rows.isEmpty
                      ? Center(
                          child: Text(
                            state.message ??
                                'No payload-set records yet. Use Ensure on a service.',
                          ),
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                          itemCount: rows.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (ctx, i) {
                            final r = rows[i];
                            final busy = state.busyService == r.service;
                            return _DatasetRow(
                              row: r,
                              busy: busy,
                              onEnsure: () => cubit.ensure(r.service),
                              onActivate: (v) => cubit.activate(r.service, v),
                              onOpen: () {
                                context.go(
                                  '${AppRoutes.specs}?spec=${Uri.encodeComponent(r.service)}&tab=data',
                                );
                              },
                            );
                          },
                        ),
            ),
          ],
        );
      },
    );
  }
}

class _DatasetRow extends StatelessWidget {
  const _DatasetRow({
    required this.row,
    required this.busy,
    required this.onEnsure,
    required this.onActivate,
    required this.onOpen,
  });

  final DatasetServiceRow row;
  final bool busy;
  final VoidCallback onEnsure;
  final void Function(String version) onActivate;
  final VoidCallback onOpen;

  String _setLabel(Map<String, dynamic> s) {
    final v = s['version'] ?? '?';
    final label = s['label'] ?? 'set';
    final apis = s['api_count'] ?? 0;
    return 'v$v · $label · $apis apis';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final active = row.activeVersion;
    final n = row.sets.length;
    final sorted = [...row.sets]..sort((a, b) {
        final av = int.tryParse('${a['version']}') ?? 0;
        final bv = int.tryParse('${b['version']}') ?? 0;
        return bv.compareTo(av);
      });

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          SizedBox(
            width: 220,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(row.label, style: theme.textTheme.titleSmall),
                Text(
                  row.service,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                if (row.error != null)
                  Text(
                    friendlyApiError(row.error!),
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.error,
                    ),
                  ),
              ],
            ),
          ),
          SizedBox(
            width: 88,
            child: Text(
              active == null ? '—' : 'v$active',
              style: theme.textTheme.titleSmall?.copyWith(
                color: active == null
                    ? theme.colorScheme.onSurfaceVariant
                    : theme.colorScheme.primary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          Expanded(
            child: n == 0
                ? Text(
                    'No versions yet',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  )
                : Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.primaryContainer
                              .withValues(alpha: 0.55),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          n == 1 ? '1 version' : '$n versions',
                          style: theme.textTheme.labelMedium?.copyWith(
                            color: theme.colorScheme.onPrimaryContainer,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Flexible(
                        child: PopupMenuButton<String>(
                          tooltip: 'Pick a version to activate',
                          enabled: !busy,
                          onSelected: onActivate,
                          itemBuilder: (ctx) => [
                            for (final s in sorted)
                              PopupMenuItem(
                                value: '${s['version'] ?? ''}',
                                child: Row(
                                  children: [
                                    Icon(
                                      '${s['version']}' == '$active'
                                          ? Icons.check_circle
                                          : Icons.circle_outlined,
                                      size: 16,
                                      color: '${s['version']}' == '$active'
                                          ? theme.colorScheme.primary
                                          : theme.colorScheme.onSurfaceVariant,
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(child: Text(_setLabel(s))),
                                  ],
                                ),
                              ),
                          ],
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Flexible(
                                child: Text(
                                  sorted.isEmpty
                                      ? 'Versions'
                                      : _setLabel(
                                          sorted.firstWhere(
                                            (s) =>
                                                '${s['version']}' == '$active',
                                            orElse: () => sorted.first,
                                          ),
                                        ),
                                  overflow: TextOverflow.ellipsis,
                                  style: theme.textTheme.bodySmall,
                                ),
                              ),
                              const Icon(Icons.expand_more, size: 18),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
          ),
          const SizedBox(width: 8),
          if (busy)
            const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          else ...[
            TextButton(onPressed: onEnsure, child: const Text('Ensure')),
            TextButton(onPressed: onOpen, child: const Text('Open')),
          ],
        ],
      ),
    );
  }
}
