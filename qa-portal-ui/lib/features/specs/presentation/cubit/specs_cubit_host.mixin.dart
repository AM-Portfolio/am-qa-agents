import 'package:dio/dio.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../execute/data/execute_repository.dart';
import '../../data/specs_repository.dart';
import '../../domain/try_draft.dart';
import 'specs_state.dart';

String specsApiId(Map<String, dynamic> api, int index) =>
    '${api['id'] ?? api['operationId'] ?? index}';

/// Shared accessors for SpecsCubit mixins (fields live on [SpecsCubit]).
mixin SpecsCubitHost on Cubit<SpecsState> {
  SpecsRepository get repo;
  ExecuteRepository get executeRepo;
  Dio get dio;
  TryHistory get history;
  Map<String, dynamic>? get pendingImportCollection;
  set pendingImportCollection(Map<String, dynamic>? v);
  int get loadGen;
  set loadGen(int v);
  String? get apisFetchedFor;
  set apisFetchedFor(String? v);

  void pushDraftHistory();
  Future<void> ensureToken({bool force = false});
  String prettyJson(Object? value);
  String prettyResponseBody(dynamic data);
  Map<String, dynamic>? matchConfig(String service, String environment);
  String? openapiVersion();
  String? extractOpenapiUrl(Map<String, dynamic> doc);
  Map<String, dynamic>? stableDoc(Map<String, dynamic> envelope);
  String specRevisionFor({
    required String service,
    required String docVersion,
    required String pathCount,
    String? payloadVersion,
  });
  Future<void> loadPayloadSets(
    String service, {
    bool resetVersion = false,
    bool hydrate = true,
  });
  Future<void> hydrateDataFromSet(String service, String? version);
  Future<void> loadOpenapiDoc(String service);
  Future<void> applyApiToDraft(Map<String, dynamic> api, {bool pushHistory = true});
  void applyPayloadMap(Map<String, dynamic> payload, {bool pushHistory = true});
  Future<void> loadSetApiIntoTry({bool pushHistory = true});
  Future<void> ensureMcpTools({bool force = false});
  Future<void> ensureForWorkspaceTab(SpecsWorkspaceTab tab);
  Future<void> ensurePayloadSetList({bool resetVersion = false});
  Future<void> ensurePayloadVersion(String? version);
  Future<void> ensureWorkspacePayload();
  Future<void> applyProfileDefaults({
    String? environment,
    String? service,
    String? payloadVersion,
  });
  Future<void> ensureApis({bool force = false});
  Future<void> ensureTestDraft();
  Future<void> ensureOpenapiDoc({bool force = false});
  Future<void> ensureOverview({bool force = false});
  Future<void> selectService(String service);
  Future<void> refreshOpenapiTools();
  Future<void> loadOverview();
  Future<void> pickApi(Map<String, dynamic> api);
  Future<void> runTry();
  String curlForPayloadRow(Map<String, dynamic> row);
  Future<({int? status, int? ms, String body})> quickTestPayloadRow(
    Map<String, dynamic> row,
  );
  Future<void> ensureWorking({bool apply = true, bool pushHistory = true});
  Future<void> setPayloadVersion(String? version);
  Future<String?> runLoad({bool mockOne = false});
  void revertDraft();
  Map<String, dynamic>? findSetEntry(
    Map apis, {
    required String apiId,
    String? method,
    String? path,
  });
}
