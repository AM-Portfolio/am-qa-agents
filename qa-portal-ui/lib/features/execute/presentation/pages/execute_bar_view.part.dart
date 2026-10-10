part of 'execute_bar.dart';

class _ExecuteBarView extends StatelessWidget {
  const _ExecuteBarView({
    required this.apiOk,
    this.apiMessage,
    this.onClearCache,
  });

  final bool apiOk;
  final String? apiMessage;
  final VoidCallback? onClearCache;

  Future<void> _pickApis(BuildContext context) async {
    final cubit = context.read<_ExecuteCubit>();
    final state = cubit.state;
    if (state.catalogApis.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No APIs for this profile service')),
      );
      return;
    }
    final selected = Set<String>.from(state.selectedApiIds);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setLocal) {
            return AlertDialog(
              title: Text('Pick APIs (${selected.length}/${state.catalogApis.length})'),
              content: SizedBox(
                width: 520,
                height: 420,
                child: Column(
                  children: [
                    Row(
                      children: [
                        TextButton(
                          onPressed: () => setLocal(() {
                            selected
                              ..clear()
                              ..addAll(
                                state.catalogApis.map(
                                  (a) => '${a['id'] ?? a['operationId'] ?? ''}',
                                ).where((e) => e.isNotEmpty),
                              );
                          }),
                          child: const Text('Select all'),
                        ),
                        TextButton(
                          onPressed: () => setLocal(selected.clear),
                          child: const Text('Clear'),
                        ),
                      ],
                    ),
                    Expanded(
                      child: ListView.builder(
                        itemCount: state.catalogApis.length,
                        itemBuilder: (_, i) {
                          final a = state.catalogApis[i];
                          final id = '${a['id'] ?? a['operationId'] ?? i}';
                          final method = '${a['method'] ?? ''}'.toUpperCase();
                          final path = '${a['path'] ?? a['url'] ?? ''}';
                          return CheckboxListTile(
                            dense: true,
                            value: selected.contains(id),
                            title: Text('$method $path'),
                            subtitle: Text(id),
                            onChanged: (v) => setLocal(() {
                              if (v == true) {
                                selected.add(id);
                              } else {
                                selected.remove(id);
                              }
                            }),
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Apply')),
              ],
            );
          },
        );
      },
    );
    if (ok == true) cubit.setSelectedApis(selected);
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 6),
        child: GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          child: BlocBuilder<_ExecuteCubit, _ExecuteState>(
            builder: (context, state) {
              final needsUi =
                  state.testType == 'playwright' || state.testType == 'mixed';
              final cfg = state.selectedConfig;
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Text(
                        'Execute',
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                              color: AppColors.primary,
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                      const SizedBox(width: 8),
                      Chip(
                        visualDensity: VisualDensity.compact,
                        avatar: Icon(
                          Icons.favorite,
                          size: 12,
                          color: apiOk
                              ? Colors.green
                              : Theme.of(context).colorScheme.error,
                        ),
                        label: Text(
                          apiOk ? 'api ok' : (apiMessage ?? 'api down'),
                          style: const TextStyle(fontSize: 11),
                        ),
                      ),
                      const Spacer(),
                      if (onClearCache != null)
                        TextButton.icon(
                          onPressed: onClearCache,
                          icon: const Icon(Icons.cleaning_services, size: 16),
                          label: const Text('Clear cache'),
                        ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      _dd(
                        width: 220,
                        label: 'Config',
                        value: state.configId,
                        items: [
                          for (final c in state.configs)
                            DropdownMenuItem(
                              value: '${c['id']}',
                              child: Text(
                                _configLabel(c),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                        ],
                        onChanged: state.busy
                            ? null
                            : (v) =>
                                context.read<_ExecuteCubit>().selectConfig(v),
                      ),
                      if (state.configEnvironment != null)
                        Chip(
                          visualDensity: VisualDensity.compact,
                          label: Text(
                            'env ${state.configEnvironment}',
                            style: const TextStyle(fontSize: 11),
                          ),
                        ),
                      if (state.payloadSetVersion != null)
                        Chip(
                          visualDensity: VisualDensity.compact,
                          avatar: const Icon(Icons.storage_outlined, size: 14),
                          label: Text(
                            'data v${state.payloadSetVersion}',
                            style: const TextStyle(fontSize: 11),
                          ),
                        )
                      else if (state.configService != null)
                        Chip(
                          visualDensity: VisualDensity.compact,
                          label: Text(
                            'data · active',
                            style: const TextStyle(fontSize: 11),
                          ),
                        ),
                      _dd(
                        width: 110,
                        label: 'Preset',
                        value: state.preset,
                        items: const [
                          DropdownMenuItem(value: 'custom', child: Text('custom')),
                          DropdownMenuItem(value: 'smoke', child: Text('smoke 1×1')),
                          DropdownMenuItem(value: 'load', child: Text('load 20×50')),
                          DropdownMenuItem(value: '20u-50', child: Text('20u×50')),
                          DropdownMenuItem(value: 'stress', child: Text('stress')),
                        ],
                        onChanged: state.busy
                            ? null
                            : (v) {
                                if (v != null) {
                                  context.read<_ExecuteCubit>().applyPreset(v);
                                }
                              },
                      ),
                      _dd(
                        width: 120,
                        label: 'Runner',
                        value: state.testType,
                        items: const [
                          DropdownMenuItem(value: 'k6', child: Text('API (k6)')),
                          DropdownMenuItem(
                            value: 'playwright',
                            child: Text('UI (PW)'),
                          ),
                          DropdownMenuItem(value: 'mixed', child: Text('Mixed')),
                        ],
                        onChanged: state.busy
                            ? null
                            : (v) {
                                if (v != null) {
                                  context.read<_ExecuteCubit>().setTestType(v);
                                }
                              },
                      ),
                      _dd(
                        width: 100,
                        label: 'Intensity',
                        value: state.runProfile,
                        items: const [
                          DropdownMenuItem(value: 'debug', child: Text('1-call')),
                          DropdownMenuItem(value: 'load', child: Text('load')),
                        ],
                        onChanged: state.busy
                            ? null
                            : (v) {
                                if (v != null) {
                                  context.read<_ExecuteCubit>().setRunProfile(v);
                                }
                              },
                      ),
                      SizedBox(
                        width: 72,
                        child: TextFormField(
                          key: ValueKey('vus-${state.vus}'),
                          initialValue: '${state.vus}',
                          enabled: !state.audienceLocked && !state.busy,
                          decoration: const InputDecoration(
                            labelText: 'VUs',
                            isDense: true,
                            border: OutlineInputBorder(),
                          ),
                          keyboardType: TextInputType.number,
                          onChanged: (v) {
                            final n = int.tryParse(v);
                            if (n != null) {
                              context.read<_ExecuteCubit>().setVus(n);
                            }
                          },
                        ),
                      ),
                      SizedBox(
                        width: 80,
                        child: TextFormField(
                          key: ValueKey('calls-${state.calls}'),
                          initialValue: '${state.calls}',
                          enabled: !state.audienceLocked && !state.busy,
                          decoration: const InputDecoration(
                            labelText: 'Calls',
                            isDense: true,
                            border: OutlineInputBorder(),
                          ),
                          keyboardType: TextInputType.number,
                          onChanged: (v) {
                            final n = int.tryParse(v);
                            if (n != null) {
                              context.read<_ExecuteCubit>().setCalls(n);
                            }
                          },
                        ),
                      ),
                      if (state.testType != 'playwright')
                        OutlinedButton(
                          onPressed: state.busy ? null : () => _pickApis(context),
                          child: Text(
                            state.selectedApiIds.isEmpty
                                ? 'APIs: all'
                                : 'APIs: ${state.selectedApiIds.length}',
                          ),
                        ),
                      if (needsUi) ...[
                        _dd(
                          width: 150,
                          label: 'UI flow',
                          value: state.uiProfile,
                          items: [
                            const DropdownMenuItem(
                              value: null,
                              child: Text('(none)'),
                            ),
                            for (final id in state.flowIds)
                              DropdownMenuItem(
                                value: id,
                                child: Text(id, overflow: TextOverflow.ellipsis),
                              ),
                          ],
                          onChanged: state.busy
                              ? null
                              : (v) => context
                                  .read<_ExecuteCubit>()
                                  .setUiProfile(v),
                        ),
                        _dd(
                          width: 120,
                          label: 'UI suite',
                          value: state.uiSuite,
                          items: [
                            const DropdownMenuItem(
                              value: null,
                              child: Text('(none)'),
                            ),
                            for (final id in state.suiteIds)
                              DropdownMenuItem(value: id, child: Text(id)),
                            const DropdownMenuItem(
                              value: 'smoke',
                              child: Text('smoke'),
                            ),
                            const DropdownMenuItem(
                              value: 'release_gate',
                              child: Text('release_gate'),
                            ),
                          ],
                          onChanged: state.busy
                              ? null
                              : (v) =>
                                  context.read<_ExecuteCubit>().setUiSuite(v),
                        ),
                      ],
                      FilledButton.icon(
                        onPressed: state.busy
                            ? null
                            : () async {
                                // Prefer service from /services/:id or /specs?spec=
                                final loc = GoRouterState.of(context).uri;
                                String? routeService;
                                final path = loc.path;
                                final m = RegExp(r'^/services/([^/]+)').firstMatch(path);
                                if (m != null) {
                                  routeService = Uri.decodeComponent(m.group(1)!);
                                } else {
                                  final spec = loc.queryParameters['spec'];
                                  if (spec != null && spec.isNotEmpty) {
                                    routeService = spec;
                                  }
                                }
                                final env = loc.queryParameters['env'];
                                final id = await context.read<_ExecuteCubit>().run(
                                      service: routeService,
                                      environment: env,
                                    );
                                if (id != null &&
                                    id.isNotEmpty &&
                                    context.mounted) {
                                  context.go('/runs/$id');
                                }
                              },
                        icon: state.busy
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.play_arrow, size: 18),
                        label: const Text('Run'),
                      ),
                      if (state.lastRunId != null)
                        OutlinedButton.icon(
                          onPressed: state.busy
                              ? null
                              : () => context.read<_ExecuteCubit>().stopLast(),
                          icon: const Icon(Icons.stop, size: 16),
                          label: const Text('Stop'),
                        ),
                      if (state.audienceLocked)
                        Chip(
                          label: Text('${state.audience} → 1×1'),
                          visualDensity: VisualDensity.compact,
                        ),
                      if (cfg != null)
                        Text(
                          '${cfg['service'] ?? ''}/${cfg['environment'] ?? ''}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      if (state.message != null)
                        Text(
                          state.message!,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                    ],
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  static String _configLabel(Map<String, dynamic> c) {
    final name = '${c['name'] ?? c['id'] ?? ''}'.replaceAll(RegExp(r'-+$'), '');
    final svc = '${c['service'] ?? ''}'.trim();
    final env = '${c['environment'] ?? ''}'.trim();
    if (svc.isEmpty) return name;
    return env.isEmpty ? '$name · $svc' : '$name · $svc/$env';
  }

  Widget _dd({
    required double width,
    required String label,
    required String? value,
    required List<DropdownMenuItem<String?>> items,
    required ValueChanged<String?>? onChanged,
  }) {
    return SizedBox(
      width: width,
      child: DropdownButtonFormField<String?>(
        key: ValueKey('$label-$value'),
        initialValue: value,
        isExpanded: true,
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          border: const OutlineInputBorder(),
          contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        ),
        items: items,
        onChanged: onChanged,
      ),
    );
  }
}
