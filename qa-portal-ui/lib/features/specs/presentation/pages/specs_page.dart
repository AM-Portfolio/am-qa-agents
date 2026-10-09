import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../../execute/data/execute_repository.dart';
import '../../data/specs_repository.dart';
import '../cubit/specs_cubit.dart';
import '../shell/specs_shell.dart';

export '../cubit/specs_cubit.dart';
export '../cubit/specs_state.dart';

/// Specs feature entry — Collections / Datasets, Test / Swagger / MCP / SDK / Use cases.
class SpecsPage extends StatelessWidget {
  const SpecsPage({super.key});

  static SpecsNavMode? _parseMode(String? raw) {
    switch ((raw ?? '').trim().toLowerCase()) {
      case 'datasets':
      case 'data':
        return SpecsNavMode.datasets;
      case 'collections':
        return SpecsNavMode.collections;
      default:
        return null;
    }
  }

  static SpecsWorkspaceTab? _parseTab(String? raw) {
    switch ((raw ?? '').trim().toLowerCase()) {
      case 'test':
        return SpecsWorkspaceTab.test;
      case 'swagger':
        return SpecsWorkspaceTab.swagger;
      case 'mcp':
      case 'mcp/ai':
      case 'ai':
        return SpecsWorkspaceTab.mcp;
      case 'sdk':
        return SpecsWorkspaceTab.sdk;
      case 'usecases':
      case 'use-cases':
      case 'use_cases':
        return SpecsWorkspaceTab.usecases;
      default:
        return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final q = GoRouterState.of(context).uri.queryParameters;
    final spec = q['spec'];
    final mode = _parseMode(q['mode']);
    final tab = _parseTab(q['tab']);
    final version = q['v'];
    return BlocProvider(
      create: (_) => SpecsCubit(
        getIt<SpecsRepository>(),
        getIt<ExecuteRepository>(),
        getIt<Dio>(),
      )..boot(
          initialService: spec,
          initialNavMode: mode,
          initialTab: tab,
          initialPayloadVersion: version,
        ),
      child: const SpecsShell(),
    );
  }
}
