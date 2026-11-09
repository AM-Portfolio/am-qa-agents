import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/config/connection_presets.dart';
import '../../../../core/config/portal_runtime.dart';
import '../../../../core/di/injection.dart';
import '../cubit/workspace_cubit.dart';

/// Connection + AM env + workspace env variables (one surface).
Future<void> showEnvironmentsSheet(
  BuildContext context, {
  VoidCallback? onSaved,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (ctx) {
      return BlocProvider.value(
        value: context.read<WorkspaceCubit>(),
        child: _EnvironmentsBody(onSaved: onSaved),
      );
    },
  );
}

class _EnvironmentsBody extends StatefulWidget {
  const _EnvironmentsBody({this.onSaved});

  final VoidCallback? onSaved;

  @override
  State<_EnvironmentsBody> createState() => _EnvironmentsBodyState();
}

class _EnvironmentsBodyState extends State<_EnvironmentsBody> {
  late TextEditingController _name;
  late TextEditingController _customBase;
  late String _environment;
  late String _connectionId;
  late List<(TextEditingController key, TextEditingController value)> _vars;

  @override
  void initState() {
    super.initState();
    final ws = context.read<WorkspaceCubit>().state.active;
    _name = TextEditingController(text: ws?.name ?? 'Workspace');
    _environment = ws?.environment ?? 'dev';
    final preset = ConnectionPreset.byId(ws?.connectionId) ??
        ConnectionPreset.byApiBase(ws?.apiBase) ??
        ConnectionPreset.byApiBase(
          getIt.isRegistered<PortalRuntime>()
              ? getIt<PortalRuntime>().apiBase
              : null,
        ) ??
        ConnectionPreset.local;
    _connectionId = ws?.connectionId ?? preset.id;
    _customBase = TextEditingController(
      text: ws?.apiBase ?? preset.apiBase,
    );
    final entries = (ws?.variables ?? const <String, String>{}).entries.toList();
    if (entries.isEmpty) {
      _vars = [
        (
          TextEditingController(text: 'base_url'),
          TextEditingController(),
        ),
      ];
    } else {
      _vars = [
        for (final e in entries)
          (TextEditingController(text: e.key), TextEditingController(text: e.value)),
      ];
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _customBase.dispose();
    for (final v in _vars) {
      v.$1.dispose();
      v.$2.dispose();
    }
    super.dispose();
  }

  Map<String, String> _collectVars() {
    final out = <String, String>{};
    for (final v in _vars) {
      final k = v.$1.text.trim();
      if (k.isEmpty) continue;
      out[k] = v.$2.text;
    }
    return out;
  }

  Future<void> _save() async {
    final preset = ConnectionPreset.byId(_connectionId);
    final base = _connectionId == 'custom'
        ? _customBase.text.trim()
        : (preset?.apiBase ?? _customBase.text.trim());
    await context.read<WorkspaceCubit>().saveActive(
          name: _name.text.trim().isEmpty ? 'Workspace' : _name.text.trim(),
          environment: _environment,
          connectionId: _connectionId,
          apiBase: base,
          variables: _collectVars(),
        );
    if (!mounted) return;
    Navigator.pop(context);
    widget.onSaved?.call();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Saved · API ${getIt<PortalRuntime>().apiBase} · env $_environment',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bottom = MediaQuery.viewInsetsOf(context).bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + bottom),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Environments', style: theme.textTheme.titleLarge),
            const SizedBox(height: 4),
            Text(
              'Connection, AM environment, and workspace variables',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _name,
              decoration: const InputDecoration(
                labelText: 'Workspace name',
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
            const SizedBox(height: 16),
            Text('Connection', style: theme.textTheme.titleSmall),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final p in ConnectionPreset.all)
                  ChoiceChip(
                    label: Text(p.label),
                    selected: _connectionId == p.id,
                    onSelected: (_) {
                      setState(() {
                        _connectionId = p.id;
                        _customBase.text = p.apiBase;
                      });
                    },
                  ),
                ChoiceChip(
                  label: const Text('Custom'),
                  selected: _connectionId == 'custom',
                  onSelected: (_) => setState(() => _connectionId = 'custom'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _customBase,
              enabled: _connectionId == 'custom' ||
                  ConnectionPreset.byId(_connectionId) != null,
              decoration: const InputDecoration(
                labelText: 'API base',
                hintText: 'https://am-dev.asrax.in/qa',
                border: OutlineInputBorder(),
                isDense: true,
              ),
              onChanged: (_) {
                if (_connectionId != 'custom') {
                  setState(() => _connectionId = 'custom');
                }
              },
            ),
            const SizedBox(height: 16),
            Text('AM environment', style: theme.textTheme.titleSmall),
            const SizedBox(height: 8),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'dev', label: Text('dev')),
                ButtonSegment(value: 'preprod', label: Text('preprod')),
                ButtonSegment(value: 'prod', label: Text('prod')),
              ],
              selected: {_environment},
              onSelectionChanged: (s) =>
                  setState(() => _environment = s.first),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Text('Variables', style: theme.textTheme.titleSmall),
                const Spacer(),
                TextButton.icon(
                  onPressed: () {
                    setState(() {
                      _vars.add((
                        TextEditingController(),
                        TextEditingController(),
                      ));
                    });
                  },
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('Add'),
                ),
              ],
            ),
            const SizedBox(height: 4),
            for (var i = 0; i < _vars.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    Expanded(
                      flex: 2,
                      child: TextField(
                        controller: _vars[i].$1,
                        decoration: const InputDecoration(
                          labelText: 'Key',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      flex: 3,
                      child: TextField(
                        controller: _vars[i].$2,
                        decoration: const InputDecoration(
                          labelText: 'Value',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Remove',
                      onPressed: () {
                        setState(() {
                          _vars[i].$1.dispose();
                          _vars[i].$2.dispose();
                          _vars.removeAt(i);
                        });
                      },
                      icon: const Icon(Icons.close, size: 18),
                    ),
                  ],
                ),
              ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: _save,
              child: const Text('Save'),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}
