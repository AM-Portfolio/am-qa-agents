import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/flows_cubit.dart';
import '../cubit/flows_state.dart';

class FlowsVariablesPanel extends StatefulWidget {
  const FlowsVariablesPanel({super.key, required this.state});

  final FlowsState state;

  @override
  State<FlowsVariablesPanel> createState() => _FlowsVariablesPanelState();
}

class _FlowsVariablesPanelState extends State<FlowsVariablesPanel> {
  late final TextEditingController _varsCtrl;
  bool _saving = false;
  String? _msg;

  @override
  void initState() {
    super.initState();
    _varsCtrl = TextEditingController(text: _varsText(widget.state.runtime));
  }

  @override
  void didUpdateWidget(covariant FlowsVariablesPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.state.runtime != widget.state.runtime && !_saving) {
      final next = _varsText(widget.state.runtime);
      if (_varsCtrl.text != next) _varsCtrl.text = next;
    }
  }

  String _varsText(Map<String, dynamic>? runtime) {
    final v = runtime?['variables'];
    if (v is Map && v.isNotEmpty) {
      return const JsonEncoder.withIndent('  ').convert(v);
    }
    return '{\n  \n}';
  }

  @override
  void dispose() {
    _varsCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<FlowsCubit>();
    final rt = widget.state.runtime;
    final sets = (rt?['payload_sets'] is List)
        ? List<Map<String, dynamic>>.from(
            (rt!['payload_sets'] as List).whereType<Map>().map(
                  (e) => Map<String, dynamic>.from(e),
                ),
          )
        : <Map<String, dynamic>>[];
    final active = rt?['active_version'];
    final selected = rt?['selected_version'];
    final svc = '${rt?['payload_service'] ?? ''}';
    final isPack = (widget.state.selectedFlowId ?? '').startsWith('pack:');

    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: ListView(
              children: [
                Text(
                  'Runtime inputs',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                const SizedBox(height: 8),
                Text(
                  'env: ${widget.state.env}',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                Text(
                  'credential: ${widget.state.credentialId ?? 'SPT env default'}',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 12),
                Text(
                  'Data version (Specs)${svc.isNotEmpty ? ' · $svc' : ''}',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                const SizedBox(height: 6),
                if (sets.isEmpty)
                  Text(
                    svc.isEmpty
                        ? 'No Specs payload service for this flow'
                        : 'No payload sets yet — create one in Specs',
                    style: Theme.of(context).textTheme.bodySmall,
                  )
                else
                  DropdownButtonFormField<int>(
                    initialValue: selected is int
                        ? selected
                        : int.tryParse('$selected'),
                    decoration: const InputDecoration(
                      labelText: 'Payload set version',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    items: [
                      for (final s in sets)
                        if (int.tryParse('${s['version']}') != null)
                          DropdownMenuItem(
                            value: int.parse('${s['version']}'),
                            child: Text(
                              'v${s['version']}'
                              '${active != null && '${s['version']}' == '$active' ? ' (active)' : ''}'
                              '${selected != null && '${s['version']}' == '$selected' && '$selected' != '$active' ? ' · cued' : ''}',
                            ),
                          ),
                    ],
                    onChanged: (v) async {
                      if (v == null) return;
                      setState(() {
                        _saving = true;
                        _msg = null;
                      });
                      try {
                        await cubit.activatePayloadVersion(v, pin: !isPack);
                        setState(() => _msg = 'Data version → v$v');
                      } catch (e) {
                        setState(() => _msg = '$e');
                      } finally {
                        setState(() => _saving = false);
                      }
                    },
                  ),
                if (active != null &&
                    selected != null &&
                    '$active' == '$selected')
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Chip(
                      label: Text('cued version = active (v$active)'),
                      visualDensity: VisualDensity.compact,
                    ),
                  ),
                if (_msg != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      _msg!,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
              ],
            ),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            flex: 2,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Text(
                      'Custom variables',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    const Spacer(),
                    FilledButton(
                      onPressed: _saving || isPack
                          ? null
                          : () async {
                              setState(() {
                                _saving = true;
                                _msg = null;
                              });
                              try {
                                final parsed = jsonDecode(_varsCtrl.text);
                                if (parsed is! Map) {
                                  throw FormatException(
                                    'variables must be a JSON object',
                                  );
                                }
                                await cubit.saveVariables(
                                  Map<String, dynamic>.from(parsed),
                                );
                                setState(() => _msg = 'Variables saved');
                              } catch (e) {
                                setState(() => _msg = '$e');
                              } finally {
                                setState(() => _saving = false);
                              }
                            },
                      child: Text(isPack ? 'N/A on pack' : 'Save'),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Non-secret key/value map merged into login/body (header:X for headers).',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
                const SizedBox(height: 8),
                Expanded(
                  child: TextField(
                    controller: _varsCtrl,
                    maxLines: null,
                    expands: true,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      alignLabelWithHint: true,
                    ),
                    style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
