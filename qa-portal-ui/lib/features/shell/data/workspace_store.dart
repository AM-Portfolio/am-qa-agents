import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/config/connection_presets.dart';
import '../../../core/config/portal_config.dart';

/// Local named workspace preset (Postman-like context, not cloud workspaces).
class PortalWorkspace {
  const PortalWorkspace({
    required this.id,
    required this.name,
    required this.environment,
    this.defaultService,
    this.connectionId,
    this.apiBase,
    this.variables = const {},
  });

  final String id;
  final String name;

  /// AM target env: dig Contabo dig | preprod | prod.
  final String environment;
  final String? defaultService;

  /// [ConnectionPreset.id] or `custom`.
  final String? connectionId;

  /// Absolute QA API base (overrides bake-time when set).
  final String? apiBase;

  /// Postman-like env key/values for this workspace.
  final Map<String, String> variables;

  String resolvedApiBase({String? fallback}) {
    final custom = (apiBase ?? '').replaceAll(RegExp(r'/$'), '');
    if (custom.isNotEmpty) return custom;
    final preset = ConnectionPreset.byId(connectionId);
    if (preset != null) return preset.apiBase;
    return (fallback ?? PortalConfig.desktopDefaultApiBase)
        .replaceAll(RegExp(r'/$'), '');
  }

  PortalWorkspace copyWith({
    String? name,
    String? environment,
    String? defaultService,
    String? connectionId,
    String? apiBase,
    Map<String, String>? variables,
    bool clearService = false,
    bool clearConnection = false,
    bool clearApiBase = false,
  }) {
    return PortalWorkspace(
      id: id,
      name: name ?? this.name,
      environment: environment ?? this.environment,
      defaultService:
          clearService ? null : (defaultService ?? this.defaultService),
      connectionId:
          clearConnection ? null : (connectionId ?? this.connectionId),
      apiBase: clearApiBase ? null : (apiBase ?? this.apiBase),
      variables: variables ?? this.variables,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'environment': environment,
        if (defaultService != null) 'defaultService': defaultService,
        if (connectionId != null) 'connectionId': connectionId,
        if (apiBase != null) 'apiBase': apiBase,
        if (variables.isNotEmpty) 'variables': variables,
      };

  static PortalWorkspace fromJson(Map<String, dynamic> m) {
    final varsRaw = m['variables'];
    final vars = <String, String>{};
    if (varsRaw is Map) {
      varsRaw.forEach((k, v) {
        final key = '$k'.trim();
        if (key.isEmpty) return;
        vars[key] = '$v';
      });
    }
    return PortalWorkspace(
      id: '${m['id'] ?? ''}',
      name: '${m['name'] ?? 'Workspace'}',
      environment: '${m['environment'] ?? 'dev'}',
      defaultService: m['defaultService']?.toString(),
      connectionId: m['connectionId']?.toString(),
      apiBase: m['apiBase']?.toString(),
      variables: vars,
    );
  }
}

class WorkspaceStore {
  static const _listKey = 'qa_portal_workspaces_v1';
  static const _activeKey = 'qa_portal_active_workspace_v1';

  Future<List<PortalWorkspace>> loadAll() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_listKey);
    if (raw == null || raw.isEmpty) {
      // No apiBase/connectionId — inherit bake-time API_BASE (Local or Contabo dig).
      final seed = PortalWorkspace(
        id: 'default',
        name: 'Dev workspace',
        environment: 'dev',
      );
      await saveAll([seed]);
      await setActiveId(seed.id);
      return [seed];
    }
    try {
      final list = jsonDecode(raw);
      if (list is! List) return [];
      return list
          .whereType<Map>()
          .map((e) => PortalWorkspace.fromJson(Map<String, dynamic>.from(e)))
          .where((w) => w.id.isNotEmpty)
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> saveAll(List<PortalWorkspace> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _listKey,
      jsonEncode(items.map((e) => e.toJson()).toList()),
    );
  }

  Future<String?> activeId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_activeKey);
  }

  Future<void> setActiveId(String id) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_activeKey, id);
  }

  Future<PortalWorkspace?> active() async {
    final all = await loadAll();
    final id = await activeId();
    if (all.isEmpty) return null;
    return all.cast<PortalWorkspace?>().firstWhere(
          (w) => w?.id == id,
          orElse: () => all.first,
        );
  }

  Future<PortalWorkspace> upsert(PortalWorkspace ws) async {
    final all = await loadAll();
    final i = all.indexWhere((e) => e.id == ws.id);
    if (i >= 0) {
      all[i] = ws;
    } else {
      all.add(ws);
    }
    await saveAll(all);
    return ws;
  }

  Future<void> remove(String id) async {
    final all = await loadAll();
    all.removeWhere((e) => e.id == id);
    await saveAll(all);
    final active = await activeId();
    if (active == id && all.isNotEmpty) {
      await setActiveId(all.first.id);
    }
  }
}
