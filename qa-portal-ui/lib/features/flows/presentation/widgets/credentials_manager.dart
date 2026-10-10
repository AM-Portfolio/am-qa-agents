import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../cubit/flows_cubit.dart';
import '../cubit/flows_state.dart';

part 'credentials_status.part.dart';
part 'credentials_add_picker.part.dart';

/// n8n-style credentials browser: searchable list + Add-app wizard.
Future<void> showCredentialsManager(BuildContext context) async {
  final cubit = context.read<FlowsCubit>();
  await showDialog<void>(
    context: context,
    barrierDismissible: true,
    builder: (ctx) => BlocProvider.value(
      value: cubit,
      child: const _CredentialsManagerDialog(),
    ),
  );
}

class _CredentialsManagerDialog extends StatefulWidget {
  const _CredentialsManagerDialog();

  @override
  State<_CredentialsManagerDialog> createState() =>
      _CredentialsManagerDialogState();
}

class _CredentialsManagerDialogState extends State<_CredentialsManagerDialog> {
  final _search = TextEditingController();
  String _query = '';
  final Map<String, Map<String, dynamic>> _probeById = {};
  final Set<String> _probing = {};
  bool _probingAll = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_refreshAndProbeAll());
    });
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _refreshAndProbeAll() async {
    final cubit = context.read<FlowsCubit>();
    setState(() => _probingAll = true);
    try {
      await cubit.refreshCredentials();
      final out = await cubit.probeAllCredentials();
      final results = out['results'];
      if (results is List) {
        _probeById.clear();
        for (final r in results) {
          if (r is Map) {
            final id = '${r['id'] ?? ''}';
            if (id.isNotEmpty) {
              _probeById[id] = Map<String, dynamic>.from(r);
            }
          }
        }
      }
    } catch (_) {
      // leave prior probe map
    } finally {
      if (mounted) setState(() => _probingAll = false);
    }
  }

  Future<void> _probeOne(String id) async {
    setState(() => _probing.add(id));
    try {
      final out = await context.read<FlowsCubit>().probeCredential(id);
      _probeById[id] = out;
    } catch (e) {
      _probeById[id] = {
        'id': id,
        'ok': false,
        'status': 'error',
        'message': e.toString(),
      };
    } finally {
      if (mounted) {
        setState(() => _probing.remove(id));
      }
    }
  }

  List<Map<String, dynamic>> _filtered(List<Map<String, dynamic>> all) {
    final q = _query.trim().toLowerCase();
    if (q.isEmpty) return all;
    return all.where((c) {
      final hay = [
        c['name'],
        c['id'],
        c['kind'],
        c['auth_label'],
        c['env'],
        c['username'],
        c['base_url'],
      ].map((e) => '${e ?? ''}'.toLowerCase()).join(' ');
      return hay.contains(q);
    }).toList();
  }

  String _relTime(String? iso) {
    if (iso == null || iso.isEmpty) return '—';
    final t = DateTime.tryParse(iso);
    if (t == null) return iso;
    final d = DateTime.now().toUtc().difference(t.toUtc());
    if (d.inMinutes < 60) return 'Last updated ${d.inMinutes} min ago';
    if (d.inHours < 48) return 'Last updated ${d.inHours} hours ago';
    return 'Last updated ${d.inDays} days ago';
  }

  String _createdLabel(String? iso) {
    if (iso == null || iso.isEmpty) return '';
    final t = DateTime.tryParse(iso);
    if (t == null) return '';
    const months = [
      'January',
      'February',
      'March',
      'April',
      'May',
      'June',
      'July',
      'August',
      'September',
      'October',
      'November',
      'December',
    ];
    return 'Created ${t.day} ${months[t.month - 1]}';
  }

  IconData _iconFor(String kind) {
    switch (kind) {
      case 'identity_login':
        return Icons.badge_outlined;
      case 'http_basic':
        return Icons.lock_outline;
      case 'bearer_token':
        return Icons.vpn_key_outlined;
      case 'llm_api_key':
        return Icons.auto_awesome;
      case 'api_key_header':
        return Icons.extension_outlined;
      case 'grafana_token':
        return Icons.insights_outlined;
      case 'prometheus_endpoint':
        return Icons.speed;
      case 'cliq_webhook':
        return Icons.chat_outlined;
      case 'temporal_endpoint':
        return Icons.schedule;
      default:
        return Icons.key_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 48, vertical: 36),
      child: SizedBox(
        width: 720,
        height: 560,
        child: BlocBuilder<FlowsCubit, FlowsState>(
          builder: (context, state) {
            final rows = _filtered(state.credentials);
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 16, 8, 8),
                  child: Row(
                    children: [
                      Text(
                        'Credentials & Resource connect',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const Spacer(),
                      IconButton(
                        tooltip: 'Refresh & test connections',
                        onPressed: _probingAll ? null : _refreshAndProbeAll,
                        icon: _probingAll
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.refresh),
                      ),
                      FilledButton.icon(
                        onPressed: () => _openAddWizard(context),
                        icon: const Icon(Icons.add, size: 18),
                        label: const Text('Connect'),
                      ),
                      IconButton(
                        onPressed: () => Navigator.pop(context),
                        icon: const Icon(Icons.close),
                      ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: TextField(
                    controller: _search,
                    decoration: InputDecoration(
                      prefixIcon: const Icon(Icons.search, size: 20),
                      hintText: 'Search credentials…',
                      isDense: true,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                    onChanged: (v) => setState(() => _query = v),
                  ),
                ),
                const SizedBox(height: 8),
                const Divider(height: 1),
                Expanded(
                  child: rows.isEmpty
                      ? Center(
                          child: Text(
                            state.credentials.isEmpty
                                ? 'Nothing connected — add Identity, Grafana, Prom, Cliq, or Temporal'
                                : 'No matches',
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                        )
                      : ListView.separated(
                          itemCount: rows.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, i) {
                            final c = rows[i];
                            final kind = '${c['kind'] ?? ''}';
                            final auth =
                                '${c['auth_label'] ?? kind}'.trim();
                            final id = '${c['id']}';
                            final probe = _probeById[id];
                            final probing = _probing.contains(id) || _probingAll;
                            final meta = [
                              auth,
                              if ((c['env'] ?? '').toString().isNotEmpty)
                                'env=${c['env']}',
                              if ((c['username'] ?? '')
                                  .toString()
                                  .isNotEmpty)
                                c['username'],
                              _relTime(c['updated_at']?.toString()),
                              _createdLabel(
                                (c['created_at'] ?? c['updated_at'])
                                    ?.toString(),
                              ),
                              if (probe?['message'] != null)
                                '${probe!['message']}',
                            ].where((e) => e.toString().isNotEmpty).join(' · ');
                            return ListTile(
                              leading: CircleAvatar(
                                backgroundColor:
                                    scheme.primaryContainer.withValues(
                                  alpha: 0.45,
                                ),
                                child: Icon(
                                  _iconFor(kind),
                                  size: 20,
                                  color: scheme.onPrimaryContainer,
                                ),
                              ),
                              title: Text(
                                '${c['name'] ?? c['id']}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              subtitle: Text(
                                meta,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                              trailing: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  _StatusChip(
                                    probing: probing,
                                    probe: probe,
                                    hasSecret: c['has_secret'] == true,
                                  ),
                                  const SizedBox(width: 6),
                                  Text(
                                    '${c['scope'] ?? 'personal'}',
                                    style:
                                        Theme.of(context).textTheme.labelSmall,
                                  ),
                                  PopupMenuButton<String>(
                                    onSelected: (v) async {
                                      if (v == 'use') {
                                        context
                                            .read<FlowsCubit>()
                                            .setCredentialId(id);
                                        if (context.mounted) {
                                          Navigator.pop(context);
                                        }
                                      } else if (v == 'test') {
                                        await _probeOne(id);
                                      } else if (v == 'reconnect') {
                                        await _probeOne(id);
                                      } else if (v == 'edit') {
                                        await _openEditForm(context, c);
                                        await _probeOne(id);
                                      } else if (v == 'delete') {
                                        await context
                                            .read<FlowsCubit>()
                                            .deleteCredential(id);
                                        _probeById.remove(id);
                                        setState(() {});
                                      }
                                    },
                                    itemBuilder: (_) => const [
                                      PopupMenuItem(
                                        value: 'test',
                                        child: Text('Test connection'),
                                      ),
                                      PopupMenuItem(
                                        value: 'reconnect',
                                        child: Text('Reconnect'),
                                      ),
                                      PopupMenuItem(
                                        value: 'use',
                                        child: Text('Use in flow'),
                                      ),
                                      PopupMenuItem(
                                        value: 'edit',
                                        child: Text('Edit'),
                                      ),
                                      PopupMenuItem(
                                        value: 'delete',
                                        child: Text('Delete'),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Future<void> _openAddWizard(BuildContext context) async {
    final cubit = context.read<FlowsCubit>();
    final apps = await cubit.loadCredentialApps();
    if (!context.mounted) return;
    final selected = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) => _AddCredentialAppPicker(apps: apps),
    );
    if (selected == null || !context.mounted) return;
    await _openEditForm(context, null, app: selected);
  }

  Future<void> _openEditForm(
    BuildContext context,
    Map<String, dynamic>? existing, {
    Map<String, dynamic>? app,
  }) async {
    final kind = '${app?['kind'] ?? existing?['kind'] ?? 'identity_login'}';
    final appId =
        '${app?['id'] ?? existing?['app_id'] ?? ''}'.trim();
    final isToken = {
      'bearer_token',
      'llm_api_key',
      'api_key_header',
      'grafana_token',
      'prometheus_endpoint',
      'cliq_webhook',
      'temporal_endpoint',
    }.contains(kind);
    final isCliq = kind == 'cliq_webhook';
    final isTemporal = kind == 'temporal_endpoint';
    final needsBase = {
      'grafana_token',
      'prometheus_endpoint',
      'temporal_endpoint',
    }.contains(kind);
    final optionalSecret = {
      'prometheus_endpoint',
      'temporal_endpoint',
    }.contains(kind);
    final nameCtrl = TextEditingController(
      text: existing?['name']?.toString() ??
          (app != null ? '${app['title']}' : ''),
    );
    final userCtrl = TextEditingController(
      text: existing?['username']?.toString() ??
          (isTemporal ? 'qa-agent' : ''),
    );
    final secretCtrl = TextEditingController();
    final baseCtrl = TextEditingController(
      text: existing?['base_url']?.toString() ?? '',
    );
    var env = existing?['env']?.toString() ??
        context.read<FlowsCubit>().state.env;
    String secretLabel() {
      if (isCliq) return 'Webhook URL';
      if (kind == 'grafana_token') return 'Service account token';
      if (optionalSecret) return 'Bearer token (optional)';
      return isToken ? 'API key / token' : 'Password';
    }

    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          existing == null
              ? 'Connect · ${app?['title'] ?? kind}'
              : 'Edit · ${existing['name']}',
        ),
        content: SizedBox(
          width: 400,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameCtrl,
                decoration: const InputDecoration(labelText: 'Name'),
              ),
              DropdownButtonFormField<String>(
                value: env,
                items: const [
                  DropdownMenuItem(value: 'prod', child: Text('prod')),
                  DropdownMenuItem(value: 'preprod', child: Text('preprod')),
                  DropdownMenuItem(value: 'dev', child: Text('dev')),
                ],
                onChanged: (v) {
                  if (v != null) env = v;
                },
                decoration: const InputDecoration(labelText: 'Environment'),
              ),
              if ((!isToken || isTemporal) && !isCliq)
                TextField(
                  controller: userCtrl,
                  decoration: InputDecoration(
                    labelText: isTemporal ? 'Namespace' : 'Username',
                  ),
                ),
              if (!isCliq)
                TextField(
                  controller: baseCtrl,
                  decoration: InputDecoration(
                    labelText: needsBase
                        ? (isTemporal
                            ? 'Temporal address (required)'
                            : 'Base URL (required)')
                        : 'Base URL (optional)',
                  ),
                ),
              TextField(
                controller: secretCtrl,
                obscureText: !isCliq,
                decoration: InputDecoration(
                  labelText: secretLabel(),
                  hintText: existing != null
                      ? 'leave blank to keep existing secret'
                      : (optionalSecret ? 'optional' : 'required'),
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
            onPressed: () async {
              await context.read<FlowsCubit>().saveCredential(
                    name: nameCtrl.text.trim(),
                    username: userCtrl.text.trim(),
                    password: isToken ? '' : secretCtrl.text,
                    token: isToken ? secretCtrl.text : null,
                    kind: kind,
                    env: env,
                    baseUrl: isCliq ? '' : baseCtrl.text.trim(),
                    appId: appId,
                    id: existing?['id']?.toString(),
                  );
              if (ctx.mounted) Navigator.pop(ctx);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }
}

