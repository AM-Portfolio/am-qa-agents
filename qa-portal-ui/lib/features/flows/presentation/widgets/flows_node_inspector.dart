import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/flows_cubit.dart';
import '../cubit/flows_state.dart';
import 'flows_dialogs.dart';

/// Compact editor for the selected flow node (label / method / path / service).
class FlowsNodeInspector extends StatefulWidget {
  const FlowsNodeInspector({required this.state});

  final FlowsState state;

  @override
  State<FlowsNodeInspector> createState() => _FlowsNodeInspectorState();
}

class _FlowsNodeInspectorState extends State<FlowsNodeInspector> {
  late final TextEditingController _label;
  late final TextEditingController _path;
  late final TextEditingController _service;
  String _method = 'get';
  String? _boundId;

  @override
  void initState() {
    super.initState();
    _label = TextEditingController();
    _path = TextEditingController();
    _service = TextEditingController();
    _bind(widget.state);
  }

  @override
  void didUpdateWidget(covariant FlowsNodeInspector oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.state.selectedLogNodeId != _boundId ||
        widget.state.graph != oldWidget.state.graph) {
      _bind(widget.state);
    }
  }

  Map<String, dynamic>? _node(FlowsState state) {
    final id = state.selectedLogNodeId;
    if (id == null) return null;
    final nodes = state.graph?['nodes'];
    if (nodes is! List) return null;
    for (final raw in nodes) {
      if (raw is Map && '${raw['id']}' == id) {
        return Map<String, dynamic>.from(raw);
      }
    }
    return null;
  }

  void _bind(FlowsState state) {
    final n = _node(state);
    _boundId = state.selectedLogNodeId;
    _label.text = '${n?['label'] ?? ''}';
    _path.text = '${n?['exact_path'] ?? n?['path'] ?? ''}';
    _service.text = '${n?['service'] ?? ''}';
    final m = '${n?['method'] ?? 'get'}'.toLowerCase();
    _method = const {'get', 'post', 'put', 'patch', 'delete'}.contains(m)
        ? m
        : 'get';
  }

  @override
  void dispose() {
    _label.dispose();
    _path.dispose();
    _service.dispose();
    super.dispose();
  }

  void _apply() {
    context.read<FlowsCubit>().updateSelectedNode({
      'label': _label.text.trim(),
      'path': _path.text.trim(),
      'exact_path': _path.text.trim(),
      'service': _service.text.trim(),
      'method': _method,
    });
  }

  @override
  Widget build(BuildContext context) {
    final id = widget.state.selectedLogNodeId;
    if (id == null || id == '__manual_trigger__') {
      return const SizedBox.shrink();
    }
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        child: Row(
          children: [
            Text('Node', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(width: 8),
            SizedBox(
              width: 100,
              child: DropdownButtonFormField<String>(
                key: ValueKey('method-$_boundId-$_method'),
                initialValue: _method,
                isDense: true,
                decoration: const InputDecoration(
                  labelText: 'Method',
                  isDense: true,
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(value: 'get', child: Text('GET')),
                  DropdownMenuItem(value: 'post', child: Text('POST')),
                  DropdownMenuItem(value: 'put', child: Text('PUT')),
                  DropdownMenuItem(value: 'patch', child: Text('PATCH')),
                  DropdownMenuItem(value: 'delete', child: Text('DELETE')),
                ],
                onChanged: (v) {
                  if (v == null) return;
                  setState(() => _method = v);
                },
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              flex: 2,
              child: TextField(
                controller: _path,
                decoration: const InputDecoration(
                  labelText: 'Path',
                  isDense: true,
                  border: OutlineInputBorder(),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _service,
                decoration: const InputDecoration(
                  labelText: 'Service',
                  isDense: true,
                  border: OutlineInputBorder(),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _label,
                decoration: const InputDecoration(
                  labelText: 'Label',
                  isDense: true,
                  border: OutlineInputBorder(),
                ),
                onSubmitted: (_) => _apply(),
              ),
            ),
            const SizedBox(width: 8),
            TextButton(
              onPressed: () => pickPayloadForSelectedNode(context),
              child: const Text('Data'),
            ),
            const SizedBox(width: 4),
            TextButton(onPressed: _apply, child: const Text('Apply')),
          ],
        ),
      ),
    );
  }
}
