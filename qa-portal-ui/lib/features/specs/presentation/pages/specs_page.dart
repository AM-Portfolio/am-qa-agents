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

/// Specs feature entry — workspace, APIs, Test / Swagger / MCP / Use cases / Data.
class SpecsPage extends StatelessWidget {
  const SpecsPage({super.key});

  @override
  Widget build(BuildContext context) {
    final spec = GoRouterState.of(context).uri.queryParameters['spec'];
    return BlocProvider(
      create: (_) => SpecsCubit(
        getIt<SpecsRepository>(),
        getIt<ExecuteRepository>(),
        getIt<Dio>(),
      )..boot(initialService: spec),
      child: const SpecsShell(),
    );
  }
}
