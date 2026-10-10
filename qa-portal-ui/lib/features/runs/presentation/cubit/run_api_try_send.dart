import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../specs/domain/try_draft.dart';
import 'run_api_try_cubit.dart';
import 'run_api_try_helpers.dart';
import 'run_api_try_open.dart';

/// Send / file / save actions for [RunApiTryCubit].
mixin RunApiTrySend on Cubit<RunApiTryState>, RunApiTryOpen {
  Dio get tryDio;

  Future<void> pickFile(String field) async {
    final result = await FilePicker.platform.pickFiles(withData: true);
    if (result == null || result.files.isEmpty) return;
    final f = result.files.first;
    final bytes = f.bytes;
    if (bytes == null) {
      emit(state.copyWith(message: 'Could not read file bytes'));
      return;
    }
    final files =
        Map<String, ({String name, List<int> bytes})>.from(state.fileBytes);
    files[field] = (name: f.name, bytes: bytes);
    final fields = Map<String, String>.from(state.draft.fileFields)
      ..[field] = f.name;
    emit(
      state.copyWith(
        fileBytes: files,
        draft: state.draft.copyWith(fileFields: fields, bodyMode: 'multipart'),
      ),
    );
  }

  void removeFile(String field) {
    final files =
        Map<String, ({String name, List<int> bytes})>.from(state.fileBytes)
          ..remove(field);
    final fields = Map<String, String>.from(state.draft.fileFields)
      ..remove(field);
    emit(
      state.copyWith(
        fileBytes: files,
        draft: state.draft.copyWith(fileFields: fields),
      ),
    );
  }

  Future<void> runTry() async {
    final svc = state.service;
    final pathTemplate = state.draft.resolvedPath;
    if (svc.isEmpty || pathTemplate.isEmpty) {
      emit(state.copyWith(tryResult: 'Select service and path'));
      return;
    }
    if (pathParamRe.hasMatch(pathTemplate)) {
      emit(
        state.copyWith(
          tryResult: 'Fill path params: $pathTemplate',
          message: 'Unresolved path params',
        ),
      );
      return;
    }
    await ensureTryToken();
    emit(state.copyWith(loading: true, clearTryResult: true));
    final sw = Stopwatch()..start();
    try {
      dynamic data;
      final headers = <String, dynamic>{
        ...state.draft.headers,
        if (state.tryToken != null && state.tryToken!.isNotEmpty)
          'Authorization': 'Bearer ${state.tryToken}',
      };

      if (state.draft.bodyMode == 'multipart' && state.fileBytes.isNotEmpty) {
        final form = FormData();
        state.fileBytes.forEach((field, file) {
          form.files.add(
            MapEntry(
              field,
              MultipartFile.fromBytes(file.bytes, filename: file.name),
            ),
          );
        });
        if (state.draft.body.trim().isNotEmpty) {
          form.fields.add(MapEntry('payload', state.draft.body));
        }
        data = form;
      } else if (state.draft.bodyMode != 'none' &&
          state.draft.body.trim().isNotEmpty) {
        if (state.draft.bodyMode == 'json') {
          data = jsonDecode(state.draft.body);
          headers.putIfAbsent('Content-Type', () => 'application/json');
        } else {
          data = state.draft.body;
        }
      }

      var path =
          pathTemplate.startsWith('/') ? pathTemplate.substring(1) : pathTemplate;
      if (state.draft.queryParams.isNotEmpty) {
        final q = state.draft.queryParams.entries
            .where((e) => e.value.isNotEmpty)
            .map(
              (e) =>
                  '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}',
            )
            .join('&');
        if (q.isNotEmpty) path = '$path?$q';
      }
      final url = '/api/catalog/$svc/try/${state.environment}/$path';
      final res = await tryDio.request<dynamic>(
        url,
        data: data,
        options: Options(
          method: state.draft.method,
          headers: headers,
          validateStatus: (_) => true,
        ),
      );
      sw.stop();
      emit(
        state.copyWith(
          loading: false,
          tryStatusCode: res.statusCode,
          tryDurationMs: sw.elapsedMilliseconds,
          tryResult: prettyTryResponse(res.data),
        ),
      );
    } catch (e) {
      sw.stop();
      emit(
        state.copyWith(
          loading: false,
          tryDurationMs: sw.elapsedMilliseconds,
          tryResult: e.toString(),
        ),
      );
    }
  }

  Future<void> saveToCurrentSet() async {
    final svc = state.service;
    final apiId = state.apiId;
    if (svc.isEmpty || apiId.isEmpty) {
      emit(state.copyWith(message: 'Missing service or API id'));
      return;
    }
    final ver = state.payloadSetVersion;
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
    emit(state.copyWith(loading: true, clearMessage: true));
    try {
      await tryRepo.savePayload(
        service: svc,
        apiId: apiId,
        request: request,
        name: 'working',
        setVersion: ver == null ? null : int.tryParse(ver),
        intoSet: true,
      );
      emit(
        state.copyWith(
          loading: false,
          message: 'Saved to v${ver ?? 'active'}',
        ),
      );
    } catch (e) {
      emit(
        state.copyWith(
          loading: false,
          message: softTryErr('Save failed', e),
        ),
      );
    }
  }

  String copyCurlText() {
    var path = state.draft.resolvedPath.trim();
    if (path.isEmpty) path = '/';
    if (!path.startsWith('/')) path = '/$path';
    final q = state.draft.queryParams.entries
        .where((e) => e.value.isNotEmpty)
        .map(
          (e) =>
              '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}',
        )
        .join('&');
    final base = (state.targetUrl ?? '').trim();
    final joined = base.isEmpty ? path : joinBasePath(base, path);
    final url = q.isEmpty ? joined : '$joined?$q';
    return buildCurl(
      method: state.draft.method,
      url: url,
      headers: state.draft.headers,
      bearer: state.draft.authBearer ?? state.tryToken,
      body: state.draft.body,
      bodyMode: state.draft.bodyMode,
    );
  }
}
