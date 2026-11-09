import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/flows_cubit.dart';
import 'flow_payload_picker.dart';

void startNewFlowDraft(BuildContext context) {
  context.read<FlowsCubit>().startDraftFlow();
}

/// Meta dialog for first save of an untitled draft (n8n-style name-on-save).
Future<void> showSaveNewFlowDialog(BuildContext context) async {
  final cubit = context.read<FlowsCubit>();
  if (!cubit.state.isDraft) return;
  final idCtrl = TextEditingController();
  final titleCtrl = TextEditingController(
    text: '${cubit.state.graph?['title'] ?? ''}'.replaceAll('Untitled', ''),
  );
  var group = 'data_gen';
  var services = List<String>.from(cubit.state.catalogServices);
  if (services.isEmpty) {
    try {
      services = await cubit.listCatalogServices();
    } catch (_) {}
  }
  if (services.isEmpty) {
    services = const [
      'am-market-data',
      'am-subscription',
      'am-identity',
    ];
  }
  var service = services.contains('am-market-data')
      ? 'am-market-data'
      : services.first;
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => StatefulBuilder(
      builder: (ctx, setLocal) => AlertDialog(
        title: const Text('Save flow'),
        content: SizedBox(
          width: 400,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: idCtrl,
                decoration: const InputDecoration(
                  labelText: 'ID (optional)',
                  border: OutlineInputBorder(),
                  helperText: 'Leave blank to auto-generate AUTH_*',
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: titleCtrl,
                decoration: const InputDecoration(
                  labelText: 'Title',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: group,
                decoration: const InputDecoration(
                  labelText: 'Group',
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(value: 'market', child: Text('market')),
                  DropdownMenuItem(
                    value: 'subscription',
                    child: Text('subscription'),
                  ),
                  DropdownMenuItem(value: 'identity', child: Text('identity')),
                  DropdownMenuItem(value: 'data_gen', child: Text('data_gen')),
                  DropdownMenuItem(value: 'other', child: Text('other')),
                ],
                onChanged: (v) {
                  if (v == null) return;
                  setLocal(() => group = v);
                },
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                key: ValueKey('save-svc-$service'),
                initialValue: service,
                decoration: const InputDecoration(
                  labelText: 'Primary service',
                  border: OutlineInputBorder(),
                ),
                items: [
                  for (final s in services)
                    DropdownMenuItem(value: s, child: Text(s)),
                ],
                onChanged: (v) {
                  if (v != null) setLocal(() => service = v);
                },
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
            child: const Text('Save'),
          ),
        ],
      ),
    ),
  );
  if (ok != true || !context.mounted) return;
  try {
    final id = await cubit.persistDraft(
      id: idCtrl.text,
      title: titleCtrl.text,
      group: group,
      service: service,
    );
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(id == null ? 'Save failed' : 'Saved $id')),
      );
    }
  } catch (e) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }
}

Future<void> saveFlowsGraph(BuildContext context) async {
  final cubit = context.read<FlowsCubit>();
  if (cubit.state.isDraft) {
    await showSaveNewFlowDialog(context);
    return;
  }
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

void commitFlowToolAfter(
  BuildContext context,
  String afterNodeId,
  Map<String, dynamic> stub,
) {
  final cubit = context.read<FlowsCubit>();
  cubit.addNodeAfter(afterNodeId, stub);
  final g = cubit.state.graph;
  final nodes = g?['nodes'];
  if (nodes is List && nodes.isNotEmpty) {
    final last = nodes.last;
    if (last is Map) {
      cubit.selectLogNode('${last['id']}');
    }
  }
}

Future<void> pickPayloadForSelectedNode(BuildContext context) async {
  final cubit = context.read<FlowsCubit>();
  final id = cubit.state.selectedLogNodeId;
  if (id == null || id == '__manual_trigger__') return;
  Map<String, dynamic>? node;
  final nodes = cubit.state.graph?['nodes'];
  if (nodes is List) {
    for (final raw in nodes) {
      if (raw is Map && '${raw['id']}' == id) {
        node = Map<String, dynamic>.from(raw);
        break;
      }
    }
  }
  if (node == null) return;
  final service = '${node['service'] ?? ''}'.trim();
  if (service.isEmpty) return;
  final pick = await showFlowPayloadPicker(
    context,
    preferredApiId: '${node['payload_api_id'] ?? ''}',
    method: '${node['method'] ?? ''}',
    path: '${node['exact_path'] ?? node['path'] ?? ''}',
    loadPayloadSet: () => cubit.loadPayloadSet(service),
  );
  if (pick != null) {
    cubit.updateSelectedNode(pick);
  }
}

Future<void> showFlowsSuiteDialog(BuildContext context) async {
  final cubit = context.read<FlowsCubit>();
  var group = cubit.state.groupFilter.isNotEmpty
      ? cubit.state.groupFilter
      : 'data_gen';
  var apiPack = cubit.state.apiPackFilter;
  var services = List<String>.from(cubit.state.catalogServices);
  if (services.isEmpty) {
    try {
      services = await cubit.listCatalogServices();
    } catch (_) {}
  }
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
      final rows = await cubit.suitePreview(
        group: group.isEmpty ? null : group,
        apiPack: apiPack.isEmpty ? null : apiPack,
      );
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
                      labelText: 'Group',
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
                      DropdownMenuItem(
                        value: 'data_gen',
                        child: Text('data_gen'),
                      ),
                      DropdownMenuItem(
                        value: 'market',
                        child: Text('market'),
                      ),
                      DropdownMenuItem(
                        value: 'other',
                        child: Text('other'),
                      ),
                    ],
                    onChanged: (v) {
                      if (v == null) return;
                      setSt(() => group = v);
                      unawaited(preview(setSt));
                    },
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String?>(
                    key: ValueKey('suite-pack-$apiPack'),
                    initialValue: apiPack.isEmpty
                        ? null
                        : (services.contains(apiPack) ? apiPack : null),
                    decoration: const InputDecoration(
                      labelText: 'Service / api_pack (optional)',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    items: [
                      const DropdownMenuItem<String?>(
                        value: null,
                        child: Text('Any service'),
                      ),
                      for (final s in services)
                        DropdownMenuItem<String?>(value: s, child: Text(s)),
                    ],
                    onChanged: (v) {
                      setSt(() => apiPack = v ?? '');
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
  var services = List<String>.from(cubit.state.catalogServices);
  if (services.isEmpty) {
    try {
      services = await cubit.listCatalogServices();
    } catch (_) {}
  }
  if (services.isEmpty) {
    services = const ['am-market-data', 'am-subscription', 'am-identity'];
  }
  var service = services.contains('am-market-data')
      ? 'am-market-data'
      : services.first;
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
                    items: [
                      for (final s in services)
                        DropdownMenuItem(value: s, child: Text(s)),
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
