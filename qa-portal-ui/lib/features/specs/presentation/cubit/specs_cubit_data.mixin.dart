import 'dart:convert';

import '../../../../core/network/json_lists.dart';
import 'specs_cubit_host.mixin.dart';
import 'specs_state.dart';

mixin SpecsCubitDataMixin on SpecsCubitHost {
  Future<void> ensurePayloadSetList({bool resetVersion = false}) async {
    final svc = state.selectedService;
    if (svc == null) return;
    if (state.payloadListLoading) return;
    if (!resetVersion && state.payloadSets.isNotEmpty) return;
    final gen = loadGen;
    emit(state.copyWith(payloadListLoading: true));
    try {
      await loadPayloadSets(svc, resetVersion: resetVersion, hydrate: false);
    } finally {
      if (loadGen == gen && state.selectedService == svc) {
        emit(state.copyWith(payloadListLoading: false));
      }
    }
  }

  Future<void> ensurePayloadVersion(String? version) async {
    final svc = state.selectedService;
    if (svc == null || version == null || version.isEmpty) return;
    final gen = loadGen;
    emit(
      state.copyWith(
        selectedPayloadVersion: version,
        payloadRowsLoading: true,
        clearPayloadApiIds: true,
      ),
    );
    await hydrateDataFromSet(svc, version);
    if (loadGen == gen && state.selectedService == svc) {
      emit(state.copyWith(payloadRowsLoading: false));
    }
  }

  Future<void> loadPayloadSets(
    String service, {
    bool resetVersion = false,
    bool hydrate = true,
  }) async {
    try {
      final envelope = await repo.payloadSetsEnvelope(service);
      if (state.selectedService != service) return;
      final sets = mapList(
        envelope,
        keys: const ['sets', 'payload_sets', 'items', 'versions'],
      );
      final activeRaw = envelope['active_version'];
      final activeVer = activeRaw == null || '$activeRaw'.trim().isEmpty
          ? null
          : '$activeRaw'.trim();
      String? version;
      if (!resetVersion) {
        version = state.selectedPayloadVersion;
      }
      final versions = sets
          .map((s) => '${s['version'] ?? s['id'] ?? ''}')
          .where((v) => v.isNotEmpty)
          .toSet();
      if (version == null || !versions.contains(version) || resetVersion) {
        version = null;
        if (hydrate && sets.isNotEmpty) {
          if (activeVer != null && versions.contains(activeVer)) {
            version = activeVer;
          } else {
            final marked = sets.firstWhere(
              (s) => s['active'] == true || s['is_active'] == true,
              orElse: () => sets.first,
            );
            version = '${marked['version'] ?? marked['id'] ?? ''}';
            if (version.isEmpty) version = null;
          }
        }
      }
      emit(
        state.copyWith(
          payloadSets: sets,
          selectedPayloadVersion: version,
          activePayloadVersion: activeVer,
          clearPayloadVersion: version == null,
          clearActivePayloadVersion: activeVer == null,
          clearPayloadApiIds: true,
          clearGenerate: !hydrate,
        ),
      );
      if (!hydrate) return;
      await hydrateDataFromSet(service, version);
      if (version != null && state.selectedApiId != null) {
        await loadSetApiIntoTry(pushHistory: false);
      }
    } catch (_) {
      if (state.selectedService != service) return;
      emit(state.copyWith(
        payloadSets: const [],
        clearPayloadVersion: true,
        clearActivePayloadVersion: true,
        clearGenerate: true,
      ));
    }
  }

  /// Map payload-set file entries into Data tab rows (survives refresh).
  Future<void> hydrateDataFromSet(String service, String? version) async {
    if (version == null || version.isEmpty) {
      if (state.generateResults.isEmpty) {
        emit(state.copyWith(clearGenerate: true));
      }
      return;
    }
    // Don't wipe a fresh generate-all result for the same version.
    final summaryVer = '${state.generateSummary?['payload_set_version'] ?? ''}';
    if (state.generateResults.isNotEmpty &&
        state.generateSummary?['from_generate'] == true &&
        summaryVer == version) {
      return;
    }
    try {
      final set = await repo.getPayloadSet(service, version);
      final apis = set['apis'];
      if (apis is! Map) {
        emit(state.copyWith(clearGenerate: true));
        return;
      }
      final rows = <Map<String, dynamic>>[];
      for (final e in apis.entries) {
        final entry = e.value;
        if (entry is! Map) continue;
        final m = Map<String, dynamic>.from(entry);
        final req = m['request'] is Map
            ? Map<String, dynamic>.from(m['request'] as Map)
            : <String, dynamic>{
                'method': m['method'],
                'path': m['path'],
                'query': m['query'],
                'path_params': m['path_params'],
                'body': m['body'],
                'headers': m['headers'],
              };
        final resp = m['response'] is Map
            ? Map<String, dynamic>.from(m['response'] as Map)
            : null;
        final status = resp?['status'] ?? resp?['status_code'];
        final statusInt = status is num ? status.toInt() : int.tryParse('$status');
        final ok = statusInt != null && statusInt >= 200 && statusInt < 300;
        final meta = m['meta'] is Map ? Map<String, dynamic>.from(m['meta'] as Map) : {};
        rows.add({
          'api_id': m['api_id'] ?? e.key,
          'method': '${req['method'] ?? m['method'] ?? 'GET'}'.toUpperCase(),
          'path': '${req['path'] ?? m['path'] ?? ''}',
          'name': meta['name'] ?? m['name'],
          'ok': ok || statusInt == null,
          'final_status': statusInt,
          'source': meta['source'] ?? 'set',
          'attempts_used': 1,
          'attempts': const [],
          'request': req,
          'response': resp == null
              ? null
              : {
                  'status_code': statusInt,
                  'body': resp['body'],
                  'error': resp['error'],
                },
          'error': null,
          'payload_set_version': int.tryParse(version),
          'from_set': true,
        });
      }
      rows.sort((a, b) {
        final pa = '${a['path']}';
        final pb = '${b['path']}';
        return pa.compareTo(pb);
      });
      emit(
        state.copyWith(
          generateResults: rows,
          generateSummary: {
            'total': rows.length,
            'passed': rows.where((r) => r['ok'] == true).length,
            'failed': rows.where((r) => r['ok'] != true).length,
            'payload_set_version': version,
            'from_file': true,
          },
          // Remount Swagger with examples from this payload set.
          specRevision: specRevisionFor(
            service: service,
            docVersion: state.specRevision,
            pathCount: '${rows.length}',
            payloadVersion: version,
          ),
        ),
      );
    } catch (_) {
      // leave existing generate results
    }
  }

  Future<void> setPayloadVersion(String? version) async {
    final svc = state.selectedService;
    emit(
      state.copyWith(
        selectedPayloadVersion: version,
        clearPayloadVersion: version == null,
        payloadRowsLoading: version != null && version.isNotEmpty,
        clearGenerate: version == null,
        specRevision: specRevisionFor(
          service: svc ?? state.selectedService ?? 'none',
          docVersion: state.specRevision,
          pathCount: '${state.generateResults.length}',
          payloadVersion: version ?? '-',
        ),
      ),
    );
    if (svc != null && version != null && version.isNotEmpty) {
      await ensurePayloadVersion(version);
    } else if (svc != null) {
      emit(state.copyWith(payloadRowsLoading: false));
    }
    final api = state.selectedApi;
    if (api != null && state.navMode == SpecsNavMode.collections) {
      await applyApiToDraft(api, pushHistory: false);
    }
    if (version != null) {
      await loadSetApiIntoTry(pushHistory: false);
    } else if (api != null) {
      emit(state.copyWith(message: 'Payload version cleared — using OpenAPI examples'));
    }
  }

  Map<String, dynamic>? findSetEntry(
    Map apis, {
    required String apiId,
    String? method,
    String? path,
  }) {
    dynamic entry = apis[apiId] ?? apis[apiId.replaceAll('.', '_')];
    if (entry is Map) return Map<String, dynamic>.from(entry);
    final lower = apiId.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
    for (final e in apis.entries) {
      final k = '${e.key}'.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
      if (k == lower && e.value is Map) {
        return Map<String, dynamic>.from(e.value as Map);
      }
    }
    final m = (method ?? '').toUpperCase();
    final p = (path ?? '').trim();
    if (m.isEmpty || p.isEmpty) return null;
    for (final e in apis.entries) {
      if (e.value is! Map) continue;
      final row = Map<String, dynamic>.from(e.value as Map);
      final req = row['request'] is Map
          ? Map<String, dynamic>.from(row['request'] as Map)
          : row;
      final rm = '${req['method'] ?? ''}'.toUpperCase();
      final rp = '${req['path'] ?? ''}'.trim();
      if (rm == m && (rp == p || rp.endsWith(p) || p.endsWith(rp))) {
        return row;
      }
    }
    return null;
  }

  Future<void> loadSetApiIntoTry({bool pushHistory = true}) async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    final id = state.selectedApiId;
    if (svc == null || ver == null || id == null) return;
    try {
      final set = await repo.getPayloadSet(svc, ver);
      final apis = set['apis'];
      if (apis is! Map) {
        emit(state.copyWith(message: 'Payload set v$ver has no APIs'));
        return;
      }
      final selected = state.selectedApi;
      final method = '${selected?['method'] ?? state.draft.method}'.toUpperCase();
      final path = '${selected?['path'] ?? selected?['path_template'] ?? state.draft.path}';
      final entry = findSetEntry(apis, apiId: id, method: method, path: path);
      if (entry != null) {
        applyPayloadMap(entry, pushHistory: pushHistory);
        emit(state.copyWith(message: 'Loaded payload from set v$ver'));
      } else {
        emit(
          state.copyWith(
            message: 'No payload in v$ver for $method $path ($id)',
          ),
        );
      }
    } catch (e) {
      emit(state.copyWith(message: 'Failed to load set v$ver: $e'));
    }
  }

  Future<void> ensurePayloadSet() async {
    final svc = state.selectedService;
    if (svc == null) return;
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await repo.ensurePayloadSet(svc);
      await loadPayloadSets(svc);
      emit(state.copyWith(loading: false, actionResult: prettyJson(out), message: 'Payload set ensured'));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString()));
    }
  }

  Future<void> activatePayloadVersion(String version) async {
    final svc = state.selectedService;
    if (svc == null || version.isEmpty) return;
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await repo.activatePayloadSet(svc, version);
      await loadPayloadSets(svc, resetVersion: false, hydrate: false);
      emit(state.copyWith(
        loading: false,
        selectedPayloadVersion: version,
        activePayloadVersion: version,
        actionResult: prettyJson(out),
        message: 'Activated v$version',
      ));
      await ensurePayloadVersion(version);
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString()));
    }
  }

  void togglePayloadApiSelection(String apiId, {required bool selected}) {
    final next = {...state.selectedPayloadApiIds};
    if (selected) {
      next.add(apiId);
    } else {
      next.remove(apiId);
    }
    emit(state.copyWith(selectedPayloadApiIds: next));
  }

  void selectAllPayloadApis(Iterable<String> apiIds) {
    emit(state.copyWith(selectedPayloadApiIds: apiIds.toSet()));
  }

  void clearPayloadApiSelection() =>
      emit(state.copyWith(clearPayloadApiIds: true));

  Future<void> editPayloadSetApi({
    required String apiId,
    required Map<String, dynamic> request,
    Map<String, dynamic>? response,
    Map<String, dynamic>? meta,
    String name = 'working',
  }) async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    if (svc == null || ver == null) {
      emit(state.copyWith(message: 'Select a service and payload version'));
      return;
    }
    final verInt = int.tryParse(ver);
    if (verInt == null) {
      emit(state.copyWith(message: 'Invalid payload version'));
      return;
    }
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await repo.upsertPayloadSetApi(
        service: svc,
        apiId: apiId,
        version: verInt,
        request: request,
        response: response,
        meta: meta,
        name: name,
        bumpSet: false,
      );
      await loadPayloadSets(svc);
      emit(state.copyWith(
        loading: false,
        actionResult: prettyJson(out),
        message: 'Updated $apiId in v$ver',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString(), message: '$e'));
    }
  }

  Future<void> deleteSelectedPayloadApis() async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    final ids = state.selectedPayloadApiIds.toList();
    if (svc == null || ver == null || ids.isEmpty) {
      emit(state.copyWith(message: 'Select APIs to delete'));
      return;
    }
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await repo.deletePayloadSetApis(
        service: svc,
        version: ver,
        apiIds: ids,
      );
      await loadPayloadSets(svc);
      emit(state.copyWith(
        loading: false,
        clearPayloadApiIds: true,
        actionResult: prettyJson(out),
        message: 'Removed ${ids.length} API(s) from v$ver',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString(), message: '$e'));
    }
  }

  Future<void> deleteSelectedPayloadVersion() async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    if (svc == null || ver == null) {
      emit(state.copyWith(message: 'Select a payload version to delete'));
      return;
    }
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await repo.deletePayloadSet(service: svc, version: ver);
      await loadPayloadSets(svc, resetVersion: true);
      emit(state.copyWith(
        loading: false,
        clearPayloadApiIds: true,
        actionResult: prettyJson(out),
        message: 'Deleted payload set v$ver',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString(), message: '$e'));
    }
  }

  Future<void> saveToCurrentSet({bool bumpSet = false}) async {
    final svc = state.selectedService;
    final apiId = state.selectedApiId;
    if (svc == null || apiId == null) {
      emit(state.copyWith(message: 'Select a service and API'));
      return;
    }
    final ver = state.selectedPayloadVersion;
    Object? body;
    if (state.draft.body.trim().isNotEmpty && state.draft.bodyMode != 'none') {
      try {
        body = jsonDecode(state.draft.body);
      } catch (_) {
        body = state.draft.body;
      }
    }
    final request = <String, dynamic>{
      'method': state.draft.method,
      'path': state.draft.path,
      if (state.draft.pathParams.isNotEmpty) 'path_params': state.draft.pathParams,
      if (state.draft.queryParams.isNotEmpty) 'query': state.draft.queryParams,
      if (state.draft.headers.isNotEmpty) 'headers': state.draft.headers,
      if (body != null) 'body': body,
    };
    emit(state.copyWith(loading: true, message: null, clearActionResult: true));
    try {
      final out = await repo.savePayload(
        service: svc,
        apiId: apiId,
        request: request,
        name: 'working',
        setVersion: ver == null ? null : int.tryParse(ver),
        intoSet: true,
        bumpSet: bumpSet,
      );
      await loadPayloadSets(svc);
      emit(state.copyWith(
        loading: false,
        actionResult: prettyJson(out),
        message: bumpSet ? 'Saved + bumped set' : 'Saved to v${ver ?? 'active'}',
      ));
    } catch (e) {
      emit(state.copyWith(loading: false, actionResult: e.toString(), message: '$e'));
    }
  }
}
