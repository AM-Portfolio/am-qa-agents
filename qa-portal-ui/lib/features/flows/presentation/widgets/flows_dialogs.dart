import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/flows_cubit.dart';
import 'flow_tool_picker.dart';

Future<void> saveFlowsGraph(BuildContext context) async {
  final cubit = context.read<FlowsCubit>();
  try {
    final id = await cubit.saveGraph();
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(id == null ? 'Nothing to save' : 'Saved $id')),
      );
    }
  } catch (e) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }
}

Future<void> addFlowToolAfter(
  BuildContext context,
  String afterNodeId,
) async {
  final cubit = context.read<FlowsCubit>();
  final graph = cubit.state.graph;
  String svc = 'am-subscription';
  if (graph != null && graph['nodes'] is List) {
    for (final raw in graph['nodes'] as List) {
      if (raw is Map && '${raw['id']}' == afterNodeId) {
        final s = '${raw['service'] ?? ''}';
        if (s.isNotEmpty) svc = s;
        break;
      }
    }
  }
  if (svc.isEmpty) {
    final g = '${graph?['group'] ?? ''}';
    svc = g == 'identity' ? 'am-identity' : 'am-subscription';
  }
  final stub = await showFlowToolPicker(
    context,
    listTools: cubit.listOpenApiTools,
    initialService: svc,
  );
  if (stub != null) {
    cubit.addNodeAfter(afterNodeId, stub);
  }
}

Future<void> showFlowsSuiteDialog(BuildContext context) async {
  final cubit = context.read<FlowsCubit>();
  var group = 'subscription';
  var loading = false;
  var error = '';
  var flows = <Map<String, dynamic>>[];
  final selected = <String>{};

  Future<void> preview(StateSetter setSt) async {
    setSt(() {
      loading = true;
      error = '';
    });
    try {
      final rows = await cubit.suitePreview(group: group);
      setSt(() {
        flows = rows;
        selected
          ..clear()
          ..addAll(rows.map((f) => '${f['id']}'));
        loading = false;
      });
    } catch (e) {
      setSt(() {
        loading = false;
        error = '$e';
      });
    }
  }

  await showDialog<void>(
    context: context,
    builder: (ctx) {
      return StatefulBuilder(
        builder: (ctx, setSt) {
          if (!loading && flows.isEmpty && error.isEmpty) {
            unawaited(preview(setSt));
          }
          return AlertDialog(
            title: const Text('Run suite'),
            content: SizedBox(
              width: 480,
              height: 420,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  DropdownButtonFormField<String>(
                    key: ValueKey('suite-group-$group'),
                    initialValue: group,
                    decoration: const InputDecoration(
                      labelText: 'Service / group',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    items: const [
                      DropdownMenuItem(
                        value: 'identity',
                        child: Text('identity'),
                      ),
                      DropdownMenuItem(
                        value: 'subscription',
                        child: Text('subscription'),
                      ),
                    ],
                    onChanged: (v) {
                      if (v == null) return;
                      setSt(() => group = v);
                      unawaited(preview(setSt));
                    },
                  ),
                  const SizedBox(height: 8),
                  if (loading) const LinearProgressIndicator(minHeight: 2),
                  if (error.isNotEmpty)
                    Text(
                      error,
                      style: TextStyle(color: Theme.of(ctx).colorScheme.error),
                    ),
                  Expanded(
                    child: ListView(
                      children: [
                        for (final f in flows)
                          CheckboxListTile(
                            dense: true,
                            value: selected.contains('${f['id']}'),
                            title: Text('${f['title'] ?? f['id']}'),
                            subtitle: Text(
                              '${f['id']} · ${f['category'] ?? ''}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            onChanged: (on) {
                              setSt(() {
                                final id = '${f['id']}';
                                if (on == true) {
                                  selected.add(id);
                                } else {
                                  selected.remove(id);
                                }
                              });
                            },
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: selected.isEmpty
                    ? null
                    : () async {
                        try {
                          final out = await cubit.runSuite(selected.toList());
                          if (ctx.mounted) {
                            Navigator.pop(ctx);
                            ScaffoldMessenger.of(ctx).showSnackBar(
                              SnackBar(
                                content: Text(
                                  'Suite ${out['suite_run_id']} · ${out['count']} flows',
                                ),
                              ),
                            );
                          }
                        } catch (e) {
                          if (ctx.mounted) {
                            ScaffoldMessenger.of(ctx).showSnackBar(
                              SnackBar(content: Text('$e')),
                            );
                          }
                        }
                      },
                child: Text('Run ${selected.length} flows'),
              ),
            ],
          );
        },
      );
    },
  );
}

Future<void> showFlowsProposeDialog(BuildContext context) async {
  final cubit = context.read<FlowsCubit>();
  var service = 'am-subscription';
  final proposals = <Map<String, dynamic>>[];
  var loading = false;
  var error = '';
  await showDialog<void>(
    context: context,
    builder: (ctx) {
      return StatefulBuilder(
        builder: (ctx, setLocal) {
          return AlertDialog(
            title: const Text('Propose scenarios'),
            content: SizedBox(
              width: 480,
              height: 420,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  DropdownButtonFormField<String>(
                    initialValue: service,
                    items: const [
                      DropdownMenuItem(
                        value: 'am-subscription',
                        child: Text('am-subscription'),
                      ),
                      DropdownMenuItem(
                        value: 'am-identity',
                        child: Text('am-identity'),
                      ),
                    ],
                    onChanged: (v) {
                      if (v != null) setLocal(() => service = v);
                    },
                    decoration: const InputDecoration(labelText: 'Service'),
                  ),
                  const SizedBox(height: 8),
                  FilledButton(
                    onPressed: loading
                        ? null
                        : () async {
                            setLocal(() {
                              loading = true;
                              error = '';
                              proposals.clear();
                            });
                            try {
                              final out = await cubit.proposeScenarios(
                                service: service,
                              );
                              final rows = out['proposals'];
                              setLocal(() {
                                if (rows is List) {
                                  for (final r in rows) {
                                    if (r is Map) {
                                      proposals.add(
                                        Map<String, dynamic>.from(r),
                                      );
                                    }
                                  }
                                }
                                if (out['ok'] != true) {
                                  error =
                                      '${out['error'] ?? 'propose failed'}';
                                }
                              });
                            } catch (e) {
                              setLocal(() => error = e.toString());
                            } finally {
                              setLocal(() => loading = false);
                            }
                          },
                    child: Text(loading ? 'Proposing…' : 'Generate'),
                  ),
                  if (error.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(
                        error,
                        style: TextStyle(
                          color: Theme.of(ctx).colorScheme.error,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  const SizedBox(height: 8),
                  Expanded(
                    child: proposals.isEmpty
                        ? Center(
                            child: Text(
                              loading
                                  ? 'Working…'
                                  : 'No proposals yet — click Generate',
                              style: Theme.of(ctx).textTheme.bodySmall,
                            ),
                          )
                        : ListView.builder(
                            itemCount: proposals.length,
                            itemBuilder: (_, i) {
                              final p = proposals[i];
                              return ListTile(
                                dense: true,
                                title: Text('${p['title'] ?? p['id']}'),
                                subtitle: Text(
                                  '${p['category'] ?? ''} · ${p['source'] ?? ''} · ${(p['nodes'] as List?)?.length ?? 0} nodes',
                                ),
                                trailing: TextButton(
                                  onPressed: () async {
                                    await cubit.saveProposedFlow(p);
                                    if (ctx.mounted) {
                                      ScaffoldMessenger.of(ctx).showSnackBar(
                                        SnackBar(
                                          content: Text('Saved ${p['id']}'),
                                        ),
                                      );
                                    }
                                  },
                                  child: const Text('Save'),
                                ),
                              );
                            },
                          ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Close'),
              ),
            ],
          );
        },
      );
    },
  );
}

Future<void> showFlowsScheduleDialog(BuildContext context) async {
  final cubit = context.read<FlowsCubit>();
  final fid = cubit.state.selectedFlowId;
  if (fid == null) return;
  final cronCtrl = TextEditingController(text: '0 */6 * * *');
  await showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text('Schedule $fid'),
      content: SizedBox(
        width: 360,
        child: TextField(
          controller: cronCtrl,
          decoration: const InputDecoration(
            labelText: 'Cron (min hour dom month dow)',
            hintText: '0 */6 * * *',
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () async {
            try {
              final row = await cubit.saveSchedule(cron: cronCtrl.text.trim());
              if (ctx.mounted) {
                Navigator.pop(ctx);
                ScaffoldMessenger.of(ctx).showSnackBar(
                  SnackBar(
                    content: Text(
                      'Schedule ${row['id']} · backend=${row['backend'] ?? row['sync']?['backend']}',
                    ),
                  ),
                );
              }
            } catch (e) {
              if (ctx.mounted) {
                ScaffoldMessenger.of(ctx).showSnackBar(
                  SnackBar(content: Text('$e')),
                );
              }
            }
          },
          child: const Text('Save schedule'),
        ),
      ],
    ),
  );
}
