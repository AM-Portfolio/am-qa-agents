import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../cubit/flows_cubit.dart';
import '../cubit/flows_state.dart';

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

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
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
                        'Credentials',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const Spacer(),
                      FilledButton.icon(
                        onPressed: () => _openAddWizard(context),
                        icon: const Icon(Icons.add, size: 18),
                        label: const Text('Add credential'),
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
                                ? 'No credentials yet — add Identity login or an API key'
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
                                  if (c['has_secret'] == true)
                                    Icon(
                                      Icons.check_circle,
                                      size: 16,
                                      color: scheme.primary,
                                    ),
                                  const SizedBox(width: 8),
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
                                            .setCredentialId('${c['id']}');
                                        if (context.mounted) {
                                          Navigator.pop(context);
                                        }
                                      } else if (v == 'edit') {
                                        await _openEditForm(context, c);
                                      } else if (v == 'delete') {
                                        await context
                                            .read<FlowsCubit>()
                                            .deleteCredential('${c['id']}');
                                      }
                                    },
                                    itemBuilder: (_) => const [
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
    final isToken = {
      'bearer_token',
      'llm_api_key',
      'api_key_header',
    }.contains(kind);
    final nameCtrl = TextEditingController(
      text: existing?['name']?.toString() ??
          (app != null ? '${app['title']}' : ''),
    );
    final userCtrl = TextEditingController(
      text: existing?['username']?.toString() ?? '',
    );
    final secretCtrl = TextEditingController();
    final baseCtrl = TextEditingController(
      text: existing?['base_url']?.toString() ?? '',
    );
    var env = existing?['env']?.toString() ??
        context.read<FlowsCubit>().state.env;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          existing == null
              ? 'New · ${app?['title'] ?? kind}'
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
              if (!isToken)
                TextField(
                  controller: userCtrl,
                  decoration: const InputDecoration(labelText: 'Username'),
                ),
              TextField(
                controller: secretCtrl,
                obscureText: true,
                decoration: InputDecoration(
                  labelText: isToken ? 'API key / token' : 'Password',
                  hintText: existing != null
                      ? 'leave blank to keep existing secret'
                      : 'required',
                ),
              ),
              TextField(
                controller: baseCtrl,
                decoration: const InputDecoration(
                  labelText: 'Base URL (optional)',
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
                    baseUrl: baseCtrl.text.trim(),
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

class _AddCredentialAppPicker extends StatefulWidget {
  const _AddCredentialAppPicker({required this.apps});

  final List<Map<String, dynamic>> apps;

  @override
  State<_AddCredentialAppPicker> createState() =>
      _AddCredentialAppPickerState();
}

class _AddCredentialAppPickerState extends State<_AddCredentialAppPicker> {
  final _search = TextEditingController();
  String _query = '';
  Map<String, dynamic>? _selected;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final q = _query.trim().toLowerCase();
    final apps = widget.apps.where((a) {
      if (q.isEmpty) return true;
      final hay =
          '${a['title']} ${a['kind']} ${a['auth_label']} ${a['description']}'
              .toLowerCase();
      return hay.contains(q);
    }).toList();
    return AlertDialog(
      title: Row(
        children: [
          const Expanded(child: Text('Add new credential')),
          IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.close),
          ),
        ],
      ),
      content: SizedBox(
        width: 440,
        height: 360,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Select an app or service to connect to',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _search,
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                hintText: 'Search for app…',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              onChanged: (v) => setState(() => _query = v),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: ListView.builder(
                itemCount: apps.length,
                itemBuilder: (_, i) {
                  final a = apps[i];
                  final enabled = a['enabled'] != false;
                  final selected = _selected?['id'] == a['id'];
                  return ListTile(
                    enabled: enabled,
                    selected: selected,
                    leading: Icon(
                      a['kind'] == 'llm_api_key'
                          ? Icons.auto_awesome
                          : Icons.apps_outlined,
                    ),
                    title: Text('${a['title']}'),
                    subtitle: Text(
                      '${a['auth_label']} · ${a['description'] ?? ''}',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    onTap: enabled
                        ? () => setState(() => _selected = a)
                        : null,
                  );
                },
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _selected == null
              ? null
              : () => Navigator.pop(context, _selected),
          child: const Text('Continue'),
        ),
      ],
    );
  }
}
