import '../../../../core/network/json_lists.dart';
import 'specs_cubit_host.mixin.dart';

mixin SpecsCubitUseCasesMixin on SpecsCubitHost {
  Future<void> loadOverview() async {
    final svc = state.selectedService;
    if (svc == null) return;
    emit(state.copyWith(overviewLoading: true));
    try {
      // Cached overview first — live OpenAPI fan-out is slow and blocks Use cases.
      final ov = await repo.overview(
        svc,
        environment: state.environment,
        liveOpenapi: false,
      );
      if (state.selectedService != svc) return;
      emit(state.copyWith(overviewLoading: false, overview: ov));
    } catch (e) {
      if (state.selectedService != svc) return;
      emit(
        state.copyWith(
          overviewLoading: false,
          message: 'Use cases overview unavailable: $e',
        ),
      );
    }
  }

  Future<void> generateAllPayloads() async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    emit(
      state.copyWith(
        generating: true,
        clearGenerate: true,
        message: 'Generating payloads for ${state.apis.length} APIs…',
      ),
    );
    try {
      final out = await repo.generateAllPayloads(
        service: svc,
        environment: state.environment,
      );
      final rows = mapList(out, keys: const ['results', 'items']);
      await loadPayloadSets(svc, resetVersion: false);
      final verOut = out['payload_set_version'];
      emit(
        state.copyWith(
          generating: false,
          generateResults: rows,
          generateSummary: {
            'total': out['total'],
            'passed': out['passed'],
            'failed': out['failed'],
            'payload_set_version': verOut,
            'from_generate': true,
          },
          selectedPayloadVersion:
              verOut != null ? '$verOut' : state.selectedPayloadVersion,
          message:
              'Data prep done: ${out['passed'] ?? 0} passed / ${out['failed'] ?? 0} failed'
              ' (set v${verOut ?? '?'})',
        ),
      );
    } catch (e) {
      emit(
        state.copyWith(
          generating: false,
          message: 'Generate-all failed: $e',
        ),
      );
    }
  }

  /// Start Specs onboard prep workflow; polls until steps[] report is ready.
  Future<void> startOnboardPrep() async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    emit(
      state.copyWith(
        onboarding: true,
        clearOnboard: true,
        message: 'Starting onboard prep for $svc…',
      ),
    );
    try {
      final started = await repo.startOnboard(
        service: svc,
        environment: state.environment,
        allowLlm: true,
        wait: false,
      );
      final wfId = '${started['workflow_id'] ?? ''}';
      Map<String, dynamic>? report = started['result'] is Map
          ? Map<String, dynamic>.from(started['result'] as Map)
          : null;
      if (report == null && wfId.isNotEmpty) {
        for (var i = 0; i < 90; i++) {
          await Future<void>.delayed(const Duration(seconds: 2));
          final polled = await repo.onboardStatus(
            service: svc,
            workflowId: wfId,
          );
          final status = '${polled['status'] ?? ''}';
          if (polled['result'] is Map) {
            report = Map<String, dynamic>.from(polled['result'] as Map);
            break;
          }
          if (status == 'FAILED' ||
              status == 'TERMINATED' ||
              status == 'CANCELED' ||
              status == 'TIMED_OUT') {
            emit(
              state.copyWith(
                onboarding: false,
                onboardWorkflowId: wfId,
                message: 'Onboard prep $status',
              ),
            );
            return;
          }
        }
      }
      report ??= await repo.onboardLatest(
        service: svc,
        environment: state.environment,
      );
      final steps = report?['steps'];
      final failed = report?['failed_step'];
      final ok = report?['ok'] == true;
      final n = steps is List ? steps.length : 0;
      emit(
        state.copyWith(
          onboarding: false,
          onboardWorkflowId: wfId.isEmpty ? null : wfId,
          onboardReport: report,
          message: ok
              ? 'Onboard prep ok ($n steps)${wfId.isNotEmpty ? ' · $wfId' : ''}'
              : 'Onboard prep failed at ${failed ?? '?'} ($n steps)'
                  '${wfId.isNotEmpty ? ' · $wfId' : ''}',
        ),
      );
      if (ok) {
        await selectService(svc);
      }
    } catch (e) {
      emit(
        state.copyWith(
          onboarding: false,
          message: 'Onboard prep failed: $e',
        ),
      );
    }
  }
  Future<String?> runUseCases() async {
    return runLoad(mockOne: false);
  }
  Future<String?> runLoad({bool mockOne = false}) async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service'));
      return null;
    }
    // Checked APIs win. Otherwise load/all-suites = entire OpenAPI catalog for
    // the service (null api_ids). Rail highlight alone must not shrink a load run
    // to one op (that caused api_count=1 on /health while Specs showed 19 APIs).
    List<String>? ids;
    if (state.selectedApiIds.isNotEmpty) {
      ids = state.selectedApiIds.toList();
    } else if (mockOne) {
      final one = state.selectedApiId;
      if (one != null && one.isNotEmpty) {
        ids = [one];
      } else if (state.apis.isNotEmpty) {
        ids = [specsApiId(state.apis.first, 0)];
      }
    } else {
      ids = null; // all OpenAPI ops for service
    }
    if (mockOne && (ids == null || ids.isEmpty)) {
      emit(state.copyWith(message: 'No APIs to run for $svc'));
      return null;
    }
    if (!mockOne && state.apis.isEmpty) {
      emit(state.copyWith(message: 'No OpenAPI APIs loaded for $svc'));
      return null;
    }
    final cfg = matchConfig(svc, state.environment);
    final configId = cfg == null ? '' : '${cfg['id'] ?? ''}';
    emit(state.copyWith(loading: true, message: null));
    try {
      // Prefer exact config when present; else template profile + service bind.
      final out = await executeRepo.execute(
        configId: configId.isNotEmpty ? configId : null,
        service: svc,
        audience: 'developer',
        environment: state.environment,
        testType: 'k6',
        profile: mockOne ? 'debug' : 'load',
        vus: mockOne ? 1 : 20,
        calls: mockOne ? 1 : 50,
        apiIds: ids,
        openapiVersion: openapiVersion(),
        payloadSet: state.selectedPayloadVersion,
      );
      final runId = '${out['id'] ?? out['run_id'] ?? ''}';
      emit(state.copyWith(loading: false, message: mockOne ? 'Mock 1× started' : 'Load started'));
      return runId.isEmpty ? null : runId;
    } catch (e) {
      emit(state.copyWith(loading: false, message: e.toString()));
      return null;
    }
  }
}
