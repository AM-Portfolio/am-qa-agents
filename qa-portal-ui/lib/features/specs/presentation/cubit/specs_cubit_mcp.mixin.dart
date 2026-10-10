import 'dart:convert';

import 'specs_cubit_host.mixin.dart';
import 'specs_state.dart';

/// MCP / OpenAPI tools: selection, Run tool / Run all, report state.
/// [prepareMcp] / [refreshOpenapiTools] live on catalog/test mixins.
mixin SpecsCubitMcpMixin on SpecsCubitHost {

  Map<String, dynamic> _argsFromPayloadRequest(Map? request) {
    if (request == null) return {};
    final args = <String, dynamic>{};
    final pathParams = request['path_params'];
    final query = request['query'];
    if (pathParams is Map) {
      args.addAll(Map<String, dynamic>.from(pathParams));
    }
    if (query is Map) {
      args.addAll(Map<String, dynamic>.from(query));
    }
    final body = request['body'];
    if (body is Map) {
      args.addAll(Map<String, dynamic>.from(body));
    }
    return args;
  }

  /// Prefill from selected payload-set rows (Data tab / hydrate) by method+path.
  Map<String, dynamic> _argsFromSelectedSetForTool(Map<String, dynamic> tool) {
    final method = '${tool['method'] ?? ''}'.toUpperCase();
    final path = ('${tool['path'] ?? ''}').trim().replaceAll(RegExp(r'/+$'), '');
    final pathNorm = path.isEmpty ? '/' : path;
    if (method.isEmpty) return {};
    for (final row in state.generateResults) {
      final rm = '${row['method'] ?? ''}'.toUpperCase();
      var rp = ('${row['path'] ?? ''}').trim().replaceAll(RegExp(r'/+$'), '');
      if (rp.isEmpty) rp = '/';
      if (rm != method || rp != pathNorm) continue;
      final req = row['request'] is Map
          ? Map<String, dynamic>.from(row['request'] as Map)
          : <String, dynamic>{
              'path_params': row['path_params'],
              'query': row['query'],
              'body': row['body'],
            };
      return _argsFromPayloadRequest(req);
    }
    return {};
  }

  Map<String, dynamic> _argsFromDraftForTool(Map<String, dynamic> tool) {
    final method = '${tool['method'] ?? ''}'.toUpperCase();
    final path = '${tool['path'] ?? ''}';
    final draft = state.draft;
    final draftMethod = draft.method.toUpperCase();
    final draftPath =
        draft.path.trim().isNotEmpty ? draft.path.trim() : draft.resolvedPath.trim();
    if (method.isNotEmpty &&
        path.isNotEmpty &&
        draftMethod == method &&
        (draftPath == path || draft.resolvedPath.trim() == path)) {
      final args = <String, dynamic>{
        ...draft.pathParams,
        ...draft.queryParams,
      };
      final raw = draft.body.trim();
      if (raw.isNotEmpty) {
        try {
          final decoded = jsonDecode(raw);
          if (decoded is Map) {
            args.addAll(Map<String, dynamic>.from(decoded));
          }
        } catch (_) {}
      }
      if (args.isNotEmpty) return args;
    }
    // Fall back to selected data version rows (same feed as Data table).
    return _argsFromSelectedSetForTool(tool);
  }

  int? _selectedPayloadSetVersion() =>
      int.tryParse(state.selectedPayloadVersion ?? '');

  void toggleMcpToolSelection(String name, {bool? selected}) {
    if (name.isEmpty) return;
    final next = Set<String>.from(state.selectedMcpToolNames);
    final on = selected ?? !next.contains(name);
    if (on) {
      next.add(name);
    } else {
      next.remove(name);
    }
    emit(state.copyWith(selectedMcpToolNames: next));
  }

  void selectAllMcpTools() {
    final names = state.mcpTools
        .map((t) => '${t['name'] ?? ''}')
        .where((n) => n.isNotEmpty)
        .toSet();
    emit(state.copyWith(selectedMcpToolNames: names));
  }

  void clearMcpToolSelection() {
    emit(state.copyWith(selectedMcpToolNames: {}));
  }

  Future<void> runMcpTool(Map<String, dynamic> tool) async {
    final svc = state.selectedService;
    final name = '${tool['name'] ?? ''}'.trim();
    if (svc == null || name.isEmpty) {
      emit(state.copyWith(message: 'Select a service and tool first'));
      return;
    }
    final args = _argsFromDraftForTool(tool);
    emit(state.copyWith(mcpRunning: true, clearMcpReport: true, message: 'Running $name…'));
    try {
      final out = await repo.callOpenapiTool(
        service: svc,
        name: name,
        environment: state.environment,
        payloadSetVersion: _selectedPayloadSetVersion(),
        arguments: args.isEmpty ? null : args,
      );
      emit(
        state.copyWith(
          mcpRunning: false,
          mcpToolReport: {
            'ok': out['ok'] == true,
            'total': 1,
            'passed': out['ok'] == true ? 1 : 0,
            'failed': out['ok'] == true ? 0 : 1,
            'results': [out],
          },
          message: null,
        ),
      );
    } catch (e) {
      emit(
        state.copyWith(
          mcpRunning: false,
          mcpToolReport: {
            'ok': false,
            'total': 1,
            'passed': 0,
            'failed': 1,
            'results': [
              {
                'ok': false,
                'tool': name,
                'error': e.toString(),
                'arguments_used': args,
              },
            ],
          },
          message: 'Run tool failed: $e',
        ),
      );
    }
  }

  Future<void> runAllMcpTools({bool selectedOnly = false}) async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    final selected = state.selectedMcpToolNames;
    if (selectedOnly && selected.isEmpty) {
      emit(state.copyWith(message: 'Select at least one tool'));
      return;
    }
    final tools = selectedOnly
        ? state.mcpTools
            .where((t) => selected.contains('${t['name'] ?? ''}'))
            .toList()
        : List<Map<String, dynamic>>.from(state.mcpTools);
    if (tools.isEmpty) {
      emit(state.copyWith(message: 'No tools to run'));
      return;
    }

    // Progressive: call one-by-one and paint the report after each tool.
    // Status stays in Report only — no sticky page banner / toast.
    final results = <Map<String, dynamic>>[];
    emit(
      state.copyWith(
        mcpRunning: true,
        mcpToolReport: {
          'ok': false,
          'total': tools.length,
          'passed': 0,
          'failed': 0,
          'results': results,
          'progress': '0/${tools.length}',
        },
        message: null,
      ),
    );

    var passed = 0;
    var failed = 0;
    for (var i = 0; i < tools.length; i++) {
      if (state.selectedService != svc) break;
      final tool = tools[i];
      final name = '${tool['name'] ?? ''}'.trim();
      if (name.isEmpty) continue;
      final args = _argsFromDraftForTool(tool);
      Map<String, dynamic> row;
      try {
        row = await repo.callOpenapiTool(
          service: svc,
          name: name,
          environment: state.environment,
          payloadSetVersion: _selectedPayloadSetVersion(),
          // null → backend fills from preferred/active payload set.
          arguments: args.isEmpty ? null : args,
        );
      } catch (e) {
        row = {
          'ok': false,
          'tool': name,
          'method': tool['method'],
          'path': tool['path'],
          'error': e.toString(),
          'arguments_used': args,
        };
      }
      if (row['ok'] == true) {
        passed++;
      } else {
        failed++;
      }
      results.add(row);
      emit(
        state.copyWith(
          mcpRunning: true,
          mcpToolReport: {
            'ok': failed == 0,
            'total': tools.length,
            'passed': passed,
            'failed': failed,
            'results': List<Map<String, dynamic>>.from(results),
            'progress': '${i + 1}/${tools.length}',
          },
          message: null,
        ),
      );
    }

    emit(
      state.copyWith(
        mcpRunning: false,
        mcpToolReport: {
          'ok': failed == 0 && results.isNotEmpty,
          'total': results.length,
          'passed': passed,
          'failed': failed,
          'results': List<Map<String, dynamic>>.from(results),
          'progress': '${results.length}/${results.length}',
        },
        message: null,
      ),
    );
  }
}
