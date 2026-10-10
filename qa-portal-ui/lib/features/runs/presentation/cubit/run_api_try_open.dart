import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/runs_repository.dart';
import '../../../specs/data/specs_repository.dart';
import '../../../specs/domain/openapi_fill.dart';
import '../../../specs/domain/payload_set_helpers.dart';
import '../../../specs/domain/try_draft.dart';
import 'run_api_try_cubit.dart';
import 'run_api_try_helpers.dart';

/// Prefill / hydrate helpers for [RunApiTryCubit].
mixin RunApiTryOpen on Cubit<RunApiTryState> {
  SpecsRepository get tryRepo;
  RunsRepository? get tryRuns;
  TryHistory get tryHistory;

  Future<void> openFor({
    required Map<String, dynamic> run,
    required Map<String, dynamic> row,
  }) async {
    final service = '${run['service'] ?? ''}'.trim();
    final environment = '${run['environment'] ?? 'dev'}'.trim();
    final apiId = '${row['api_id'] ?? row['id'] ?? ''}'.trim();
    final runId = '${run['id'] ?? run['run_id'] ?? ''}'.trim();
    final failure = rowFailureText(row);
    var ver = versionFromRun(run);
    final target = '${run['target_url'] ?? run['base_url'] ?? ''}'.trim();

    final req = requestFromRow(row);
    var method = '${req['method'] ?? row['method'] ?? 'GET'}'.toUpperCase();
    var path =
        '${req['path'] ?? row['path'] ?? row['url'] ?? row['path_template'] ?? ''}'
            .trim();

    var draft = TryDraft(
      method: method.isEmpty ? 'GET' : method,
      path: path,
      pathParams: pathParamsFromTemplate(path),
      headers: const {'Accept': 'application/json'},
    );
    draft = applyRequestOntoDraft(draft, req);
    draft = withPathParamsFromTemplate(normalizeBodyMode(draft));

    emit(
      state.copyWith(
        service: service,
        environment: environment.isEmpty ? 'dev' : environment,
        apiId: apiId,
        payloadSetVersion: ver,
        targetUrl: target.isEmpty ? null : target,
        runFailure: failure,
        draft: draft.copyWith(
          body:
              draft.bodyMode == 'json' ? prettyJsonValue(draft.body) : draft.body,
        ),
        fileBytes: const {},
        clearTryResult: true,
        clearMessage: true,
        canRevert: false,
      ),
    );
    tryHistory.clear();
    await ensureTryToken();

    if (draftNeedsExampleFill(state.draft) &&
        runId.isNotEmpty &&
        apiId.isNotEmpty) {
      await hydrateFromTrace(runId, apiId);
    }

    if (service.isNotEmpty && ver == null) {
      ver = await resolveActiveVersion(service);
      if (ver != null) emit(state.copyWith(payloadSetVersion: ver));
    }

    var loaded = false;
    if (service.isNotEmpty && apiId.isNotEmpty && ver != null) {
      loaded = await loadSetIntoTry();
    }
    if (state.draft.path.isNotEmpty) {
      await ensureWorkingIntoTry();
    } else if (!loaded) {
      emit(
        state.copyWith(
          message: 'No path on run row — cannot prefill Test for $apiId',
        ),
      );
    }

    if (draftNeedsExampleFill(state.draft)) {
      await seedFromBuildAndOpenApi();
    }
    emit(
      state.copyWith(
        draft: normalizeBodyMode(withPathParamsFromTemplate(state.draft)),
      ),
    );
  }

  Future<void> hydrateFromTrace(String runId, String apiId) async {
    final runs = tryRuns;
    if (runs == null) return;
    try {
      final traces = await runs.traces(runId, apiId: apiId, limit: 5);
      for (final t in traces) {
        final req = requestFromTrace(t);
        if (req == null) continue;
        final next = normalizeBodyMode(
          withPathParamsFromTemplate(applyRequestOntoDraft(state.draft, req)),
        );
        emit(
          state.copyWith(
            draft: next.copyWith(
              body: next.bodyMode == 'json'
                  ? prettyJsonValue(next.body)
                  : next.body,
            ),
            message: 'Loaded request from run trace',
          ),
        );
        return;
      }
    } catch (_) {}
  }

  Future<void> seedFromBuildAndOpenApi() async {
    if (state.service.isEmpty || state.draft.path.isEmpty) return;
    try {
      final out = await tryRepo.buildPayload(
        service: state.service,
        environment: state.environment,
        method: state.draft.method,
        path: state.draft.path,
      );
      applyPayloadMap(out, pushHistory: false);
      emit(
        state.copyWith(
          draft: normalizeBodyMode(withPathParamsFromTemplate(state.draft)),
          message: 'Built from OpenAPI',
        ),
      );
    } catch (_) {}
    if (!draftNeedsExampleFill(state.draft)) return;
    try {
      final doc = await tryRepo.openapi(
        state.service,
        environment: state.environment,
      );
      final seeded = normalizeBodyMode(
        seedDraftFromOpenApi(
          document: doc,
          method: state.draft.method,
          path: state.draft.path,
          base: state.draft,
        ),
      );
      emit(
        state.copyWith(
          draft: withPathParamsFromTemplate(seeded),
          message: 'Seeded examples from OpenAPI',
        ),
      );
    } catch (_) {}
  }

  Future<String?> resolveActiveVersion(String service) async {
    try {
      final env = await tryRepo.payloadSetsEnvelope(service);
      final active = env['active_version'] ?? env['active'];
      if (active != null && '$active'.trim().isNotEmpty) {
        return '$active'.trim();
      }
      final sets = env['sets'] ?? env['payload_sets'] ?? env['items'];
      if (sets is List && sets.isNotEmpty && sets.first is Map) {
        final v = (sets.first as Map)['version'];
        if (v != null) return '$v';
      }
    } catch (_) {}
    return null;
  }

  Future<void> ensureWorkingIntoTry() async {
    if (state.service.isEmpty || state.draft.path.isEmpty) return;
    try {
      final out = await tryRepo.ensureWorking(
        service: state.service,
        environment: state.environment,
        method: state.draft.method,
        path: state.draft.path,
      );
      applyPayloadMap(out, pushHistory: false);
      emit(
        state.copyWith(
          draft: normalizeBodyMode(withPathParamsFromTemplate(state.draft)),
          message: 'Loaded working payload',
        ),
      );
    } catch (_) {
      emit(
        state.copyWith(
          draft: withPathParamsFromTemplate(state.draft),
          clearMessage: true,
        ),
      );
    }
  }

  Future<void> ensureTryToken({bool force = false}) async {
    if (!force && state.tryToken != null && state.tryToken!.isNotEmpty) return;
    try {
      final t = await tryRepo.tryToken(environment: state.environment);
      emit(
        state.copyWith(
          tryToken: t,
          draft: state.draft.copyWith(authBearer: t),
        ),
      );
    } catch (_) {}
  }

  Future<bool> loadSetIntoTry() async {
    final svc = state.service;
    final ver = state.payloadSetVersion;
    final id = state.apiId;
    if (svc.isEmpty || ver == null || id.isEmpty) return false;
    try {
      final set = await tryRepo.getPayloadSet(svc, ver);
      final apis = set['apis'];
      if (apis is! Map) return false;
      final entry = findSetEntry(
        apis,
        apiId: id,
        method: state.draft.method,
        path: state.draft.path.isEmpty ? null : state.draft.path,
      );
      if (entry == null) return false;
      applyPayloadMap(entry, pushHistory: false);
      emit(state.copyWith(message: 'Loaded payload from set v$ver'));
      return true;
    } catch (_) {
      return false;
    }
  }

  void applyPayloadMap(Map<String, dynamic> payload, {bool pushHistory = true}) {
    if (pushHistory) tryHistory.push(state.draft);
    final request = payload['request'] is Map
        ? Map<String, dynamic>.from(payload['request'] as Map)
        : payload;
    final next = normalizeBodyMode(
      withPathParamsFromTemplate(
        applyRequestOntoDraft(
          state.draft.copyWith(
            authBearer: state.tryToken ?? state.draft.authBearer,
          ),
          request,
        ),
      ),
    );
    final body =
        next.bodyMode == 'json' ? prettyJsonValue(next.body) : next.body;
    emit(
      state.copyWith(
        draft: next.copyWith(body: body),
        canRevert: tryHistory.canRevert,
      ),
    );
  }
}
