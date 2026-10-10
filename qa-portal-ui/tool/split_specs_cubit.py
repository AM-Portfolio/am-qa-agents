from pathlib import Path

root = Path(__file__).resolve().parents[1] / "lib/features/specs/presentation/cubit"
src_path = root / "specs_cubit.dart"
# Prefer backup if we already overwrote — use git show if needed
lines = src_path.read_text(encoding="utf-8").splitlines(keepends=True)
if len(lines) < 500:
    raise SystemExit(f"specs_cubit.dart too small ({len(lines)} lines) — restore from git first")


def slice(a: int, b: int) -> str:
    return "".join(lines[a - 1 : b])


def unprivate(s: str) -> str:
    for a, b in [
        ("_loadGen", "loadGen"),
        ("_apisFetchedFor", "apisFetchedFor"),
        ("_ensureToken", "ensureToken"),
        ("_pushHistory", "pushHistory"),
        ("_prettyJson", "prettyJson"),
        ("_prettyResponseBody", "prettyResponseBody"),
        ("_matchConfig", "matchConfig"),
        ("_openapiVersion", "openapiVersion"),
        ("_extractOpenapiUrl", "extractOpenapiUrl"),
        ("_stableDoc", "stableDoc"),
        ("_serviceHasRealApis", "serviceHasRealApis"),
        ("_orderServices", "orderServices"),
        ("_pruneEmptyServicesInBackground", "pruneEmptyServicesInBackground"),
        ("_loadPayloadSets", "loadPayloadSets"),
        ("_hydrateDataFromSet", "hydrateDataFromSet"),
        ("_specRevisionFor", "specRevisionFor"),
        ("_loadOpenapiDoc", "loadOpenapiDoc"),
        ("_findSetEntry", "findSetEntry"),
    ]:
        s = s.replace(a, b)
    return s


host_header = """import 'package:dio/dio.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../execute/data/execute_repository.dart';
import '../../data/specs_repository.dart';
import '../../domain/try_draft.dart';
import 'specs_state.dart';

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

  void pushHistory();
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
  Future<void> loadSetApiIntoTry({bool pushHistory = true});
  Future<void> ensureMcpTools({bool force = false});
  Future<void> ensureForWorkspaceTab(SpecsWorkspaceTab tab);
  Future<void> ensurePayloadSetList({bool resetVersion = false});
  Future<void> ensureApis({bool force = false});
  Future<void> ensureTestDraft();
  Future<void> ensureOpenapiDoc({bool force = false});
  Future<void> ensureOverview({bool force = false});
  Future<void> selectService(String service);
  Future<void> refreshOpenapiTools();
  Future<void> loadOverview();
  Future<void> pickApi(Map<String, dynamic> api);
  Future<void> runTry();
  Future<void> ensureWorking({bool apply = true, bool pushHistory = true});
  void revertDraft();
  Map<String, dynamic>? findSetEntry(
    Map apis, {
    required String apiId,
    String? method,
    String? path,
  });
}
"""

catalog_body = slice(176, 253) + slice(255, 433) + slice(616, 763) + slice(1083, 1128)
data_body = slice(434, 614) + slice(789, 1046) + slice(1219, 1599)
test_body = (
    slice(119, 174)
    + slice(1048, 1081)
    + slice(1130, 1217)
    + slice(1284, 1358)
    + slice(1601, 1815)
)
usecases_body = slice(765, 920) + slice(1195, 1197) + slice(1360, 1415)

main = unprivate(
    r"""import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/json_lists.dart';
import '../../../execute/data/execute_repository.dart';
import '../../data/specs_repository.dart';
import '../../domain/try_draft.dart';
import 'specs_cubit_catalog.mixin.dart';
import 'specs_cubit_data.mixin.dart';
import 'specs_cubit_host.mixin.dart';
import 'specs_cubit_mcp.mixin.dart';
import 'specs_cubit_test.mixin.dart';
import 'specs_cubit_usecases.mixin.dart';
import 'specs_state.dart';

export 'specs_state.dart';

class SpecsCubit extends Cubit<SpecsState>
    with
        SpecsCubitHost,
        SpecsCubitCatalogMixin,
        SpecsCubitTestMixin,
        SpecsCubitDataMixin,
        SpecsCubitUseCasesMixin,
        SpecsCubitMcpMixin {
  SpecsCubit(this.repo, this.executeRepo, this.dio) : super(const SpecsState());

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
      '${api['id'] ?? api['operationId'] ?? index}';

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
  void pushHistory() {
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
"""
)


def write_mixin(path: Path, name: str, body: str, imports: str) -> None:
    body = unprivate(body)
    text = f"""{imports}mixin {name} on SpecsCubitHost {{
{body}}}
"""
    path.write_text(text, encoding="utf-8")
    print(path.name, "lines", len(text.splitlines()))


cat_imp = """import 'package:dio/dio.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/json_lists.dart';
import '../../domain/try_draft.dart';
import 'specs_cubit_host.mixin.dart';
import 'specs_state.dart';

"""

data_imp = """import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/config/portal_config.dart';
import '../../../../core/di/injection.dart';
import '../../../../core/network/json_lists.dart';
import '../../domain/openapi_fill.dart';
import '../../domain/try_draft.dart';
import 'specs_cubit_host.mixin.dart';
import 'specs_state.dart';

"""

test_imp = """import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/json_lists.dart';
import '../../domain/openapi_fill.dart';
import '../../domain/try_draft.dart';
import 'specs_cubit_host.mixin.dart';
import 'specs_state.dart';

"""

uc_imp = """import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/json_lists.dart';
import 'specs_cubit_host.mixin.dart';
import 'specs_state.dart';

"""

# Backup original
backup = root / "specs_cubit.dart.bak"
if not backup.exists():
    backup.write_text("".join(lines), encoding="utf-8")
    print("backed up to", backup.name)

(root / "specs_cubit_host.mixin.dart").write_text(host_header, encoding="utf-8")
write_mixin(root / "specs_cubit_catalog.mixin.dart", "SpecsCubitCatalogMixin", catalog_body, cat_imp)
write_mixin(root / "specs_cubit_data.mixin.dart", "SpecsCubitDataMixin", data_body, data_imp)
write_mixin(root / "specs_cubit_test.mixin.dart", "SpecsCubitTestMixin", test_body, test_imp)
write_mixin(root / "specs_cubit_usecases.mixin.dart", "SpecsCubitUseCasesMixin", usecases_body, uc_imp)
(root / "specs_cubit.dart").write_text(main, encoding="utf-8")
print("specs_cubit.dart lines", len(main.splitlines()))
print("host lines", len(host_header.splitlines()))
