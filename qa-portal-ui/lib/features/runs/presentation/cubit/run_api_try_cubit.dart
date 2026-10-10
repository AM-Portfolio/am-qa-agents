import 'package:dio/dio.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/runs_repository.dart';
import '../../../specs/data/specs_repository.dart';
import '../../../specs/domain/try_draft.dart';
import 'run_api_try_helpers.dart';
import 'run_api_try_open.dart';
import 'run_api_try_send.dart';

class RunApiTryState {
  const RunApiTryState({
    this.draft = const TryDraft(),
    this.loading = false,
    this.tryResult,
    this.tryStatusCode,
    this.tryDurationMs,
    this.tryToken,
    this.message,
    this.service = '',
    this.environment = 'dev',
    this.apiId = '',
    this.payloadSetVersion,
    this.targetUrl,
    this.runFailure,
    this.canRevert = false,
    this.paramEnums = const {},
    this.fileBytes = const {},
  });

  final TryDraft draft;
  final bool loading;
  final String? tryResult;
  final int? tryStatusCode;
  final int? tryDurationMs;
  final String? tryToken;
  final String? message;
  final String service;
  final String environment;
  final String apiId;
  final String? payloadSetVersion;
  final String? targetUrl;
  final String? runFailure;
  final bool canRevert;
  final Map<String, List<String>> paramEnums;
  final Map<String, ({String name, List<int> bytes})> fileBytes;

  RunApiTryState copyWith({
    TryDraft? draft,
    bool? loading,
    String? tryResult,
    int? tryStatusCode,
    int? tryDurationMs,
    String? tryToken,
    String? message,
    String? service,
    String? environment,
    String? apiId,
    String? payloadSetVersion,
    String? targetUrl,
    String? runFailure,
    bool? canRevert,
    Map<String, List<String>>? paramEnums,
    Map<String, ({String name, List<int> bytes})>? fileBytes,
    bool clearTryResult = false,
    bool clearMessage = false,
  }) {
    return RunApiTryState(
      draft: draft ?? this.draft,
      loading: loading ?? this.loading,
      tryResult: clearTryResult ? null : (tryResult ?? this.tryResult),
      tryStatusCode: tryStatusCode ?? this.tryStatusCode,
      tryDurationMs: tryDurationMs ?? this.tryDurationMs,
      tryToken: tryToken ?? this.tryToken,
      message: clearMessage ? null : (message ?? this.message),
      service: service ?? this.service,
      environment: environment ?? this.environment,
      apiId: apiId ?? this.apiId,
      payloadSetVersion: payloadSetVersion ?? this.payloadSetVersion,
      targetUrl: targetUrl ?? this.targetUrl,
      runFailure: runFailure ?? this.runFailure,
      canRevert: canRevert ?? this.canRevert,
      paramEnums: paramEnums ?? this.paramEnums,
      fileBytes: fileBytes ?? this.fileBytes,
    );
  }
}

/// Local Specs-Try cubit for Run Report API detail (not full SpecsCubit).
class RunApiTryCubit extends Cubit<RunApiTryState>
    with RunApiTryOpen, RunApiTrySend {
  RunApiTryCubit(this._repo, this._dio, [this._runs])
      : super(const RunApiTryState());

  final SpecsRepository _repo;
  final Dio _dio;
  final RunsRepository? _runs;
  final TryHistory _history = TryHistory();

  @override
  SpecsRepository get tryRepo => _repo;
  @override
  Dio get tryDio => _dio;
  @override
  RunsRepository? get tryRuns => _runs;
  @override
  TryHistory get tryHistory => _history;

  void updateDraft(TryDraft draft) => emit(state.copyWith(draft: draft));

  void revertDraft() {
    final prev = _history.pop();
    if (prev == null) return;
    emit(
      state.copyWith(
        draft: prev,
        canRevert: _history.canRevert,
        message: 'Reverted to previous payload',
      ),
    );
  }

  Future<void> formatBody() async {
    try {
      final formatted = formatJsonBody(state.draft.body);
      if (formatted == null) return;
      emit(
        state.copyWith(
          draft: state.draft.copyWith(body: formatted, bodyMode: 'json'),
          message: 'JSON formatted',
        ),
      );
    } catch (e) {
      emit(state.copyWith(message: 'Invalid JSON: $e'));
    }
  }

  Future<void> buildPayload() async {
    if (state.service.isEmpty || state.draft.path.isEmpty) {
      emit(state.copyWith(message: 'Select an API first'));
      return;
    }
    emit(state.copyWith(loading: true, clearMessage: true));
    try {
      final out = await _repo.buildPayload(
        service: state.service,
        environment: state.environment,
        method: state.draft.method,
        path: state.draft.path,
      );
      applyPayloadMap(out);
      emit(state.copyWith(loading: false, message: 'Built from OpenAPI'));
    } catch (e) {
      emit(
        state.copyWith(
          loading: false,
          message: softTryErr('Build unavailable', e),
        ),
      );
    }
  }

  Future<void> ensureWorking() async {
    if (state.service.isEmpty || state.draft.path.isEmpty) {
      emit(state.copyWith(message: 'Select an API first'));
      return;
    }
    emit(state.copyWith(loading: true, clearMessage: true));
    try {
      final out = await _repo.ensureWorking(
        service: state.service,
        environment: state.environment,
        method: state.draft.method,
        path: state.draft.path,
      );
      applyPayloadMap(out);
      emit(
        state.copyWith(
          loading: false,
          draft: withPathParamsFromTemplate(state.draft),
          message: 'Working payload ready',
        ),
      );
    } catch (_) {
      await seedFromBuildAndOpenApi();
      emit(state.copyWith(loading: false));
    }
  }

  Future<void> refreshPayload() async {
    _history.push(state.draft);
    try {
      await ensureWorking();
    } catch (_) {
      final prev = _history.pop();
      if (prev != null) {
        emit(
          state.copyWith(
            draft: prev,
            canRevert: _history.canRevert,
            message: 'Refresh failed — restored previous payload',
          ),
        );
      }
    }
  }
}
