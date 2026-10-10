part of 'credentials_manager.dart';

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

  IconData _pickerIcon(String kind) {
    switch (kind) {
      case 'llm_api_key':
        return Icons.auto_awesome;
      case 'grafana_token':
        return Icons.insights_outlined;
      case 'prometheus_endpoint':
        return Icons.speed;
      case 'cliq_webhook':
        return Icons.chat_outlined;
      case 'temporal_endpoint':
        return Icons.schedule;
      default:
        return Icons.apps_outlined;
    }
  }

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
              'Select an app or resource to connect (auth, Grafana, Prom, Cliq, Temporal)',
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
                    leading: Icon(_pickerIcon('${a['kind']}')),
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
