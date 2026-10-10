import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/di/injection.dart';
import '../../../execute/data/execute_repository.dart';
import '../../data/specs_repository.dart';
import '../../domain/openapi_fill.dart';
import '../../domain/try_draft.dart';
import 'specs_cubit_catalog.mixin.dart';
import 'specs_cubit_data.mixin.dart';
import 'specs_cubit_data_io.mixin.dart';
import 'specs_cubit_host.mixin.dart';
import 'specs_cubit_mcp.mixin.dart';
import 'specs_cubit_test.mixin.dart';
import 'specs_cubit_usecases.mixin.dart';
import 'specs_profile_defaults.dart';
import 'specs_state.dart';

export 'specs_state.dart';

class SpecsCubit extends Cubit<SpecsState>
    with
        SpecsCubitHost,
        SpecsCubitCatalogMixin,
        SpecsCubitTestMixin,
        SpecsCubitDataMixin,
        SpecsCubitDataIoMixin,
        SpecsCubitUseCasesMixin,
        SpecsCubitMcpMixin {
  SpecsCubit(this.repo, this.executeRepo, this.dio) : super(const SpecsState()) {
    if (getIt.isRegistered<SpecsProfileDefaults>()) {
      getIt<SpecsProfileDefaults>().liveCubit = this;
    }
  }

  @override
  Future<void> close() {
    if (getIt.isRegistered<SpecsProfileDefaults>()) {
      final d = getIt<SpecsProfileDefaults>();
      if (identical(d.liveCubit, this)) d.liveCubit = null;
    }
    return super.close();
  }

  @override
  final SpecsRepository repo;
  @override
  final ExecuteRepository executeRepo;
  @override
  final Dio dio;
  @override
  final TryHistory history = TryHistory();
  @override
  Map<String, dynamic>? pendingImportCollection;
  @override
  int loadGen = 0;
  @override
  String? apisFetchedFor;

  static String apiId(Map<String, dynamic> api, int index) =>
      specsApiId(api, index);

  @override
  String prettyJson(Object? value) => prettyJsonValue(value);

  @override
  String prettyResponseBody(dynamic data) {
    if (data == null) return 'null';
    if (data is String) {
      final t = data.trim();
      if (t.isEmpty) return '';
      try {
        return prettyJsonValue(jsonDecode(t));
      } catch (_) {
        return data;
      }
    }
    return prettyJsonValue(data);
  }

  @override
  void pushDraftHistory() {
    history.push(state.draft);
    emit(state.copyWith(canRevert: history.canRevert));
  }

  void updateDraft(TryDraft draft) => emit(state.copyWith(draft: draft));

  @override
  void revertDraft() {
    final prev = history.pop();
    if (prev == null) return;
    emit(state.copyWith(
      draft: prev,
      canRevert: history.canRevert,
      message: 'Reverted to previous payload',
    ));
  }

  @override
  Map<String, dynamic>? matchConfig(String service, String environment) {
    for (final c in state.configs) {
      final svc = '${c['service'] ?? ''}';
      final env = '${c['environment'] ?? ''}';
      if (svc == service && (env.isEmpty || env == environment)) return c;
    }
    for (final c in state.configs) {
      if ('${c['service'] ?? ''}' == service) return c;
    }
    return null;
  }

  @override
  String? openapiVersion() {
    final info = state.openapiDocument?['info'] ?? state.openapi?['info'];
    if (info is Map && info['version'] != null) return '${info['version']}';
    return null;
  }

  @override
  String? extractOpenapiUrl(Map<String, dynamic> doc) {
    for (final key in ['openapi_url', 'openapi_url_cluster', 'source_url', 'url']) {
      final v = '${doc[key] ?? ''}'.trim();
      if (v.isNotEmpty) return v;
    }
    return null;
  }

  @override
  Map<String, dynamic>? stableDoc(Map<String, dynamic> envelope) {
    final raw = envelope['document'];
    if (raw is Map) return Map<String, dynamic>.from(raw);
    if (envelope.containsKey('paths')) return Map<String, dynamic>.from(envelope);
    return null;
  }

  @override
  Future<void> ensureToken({bool force = false}) async {
    if (!force && state.tryToken != null && state.tryToken!.isNotEmpty) return;
    try {
      final t = await repo.tryToken(environment: state.environment);
      emit(state.copyWith(tryToken: t, draft: state.draft.copyWith(authBearer: t)));
    } catch (_) {}
  }

  @override
  String specRevisionFor({
    required String service,
    required String docVersion,
    required String pathCount,
    String? payloadVersion,
  }) {
    final pv = payloadVersion ?? state.selectedPayloadVersion ?? '-';
    return '$service|${state.environment}|$docVersion|$pathCount|pv=$pv';
  }
}
