import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/di/injection.dart';
import '../../../specs/presentation/cubit/specs_profile_defaults.dart';
import '../../data/execute_repository.dart';

part 'execute_state_cubit.part.dart';
part 'execute_bar_view.part.dart';

class ExecuteBar extends StatelessWidget {
  const ExecuteBar({
    super.key,
    this.apiOk = false,
    this.apiMessage,
    this.onClearCache,
  });

  final bool apiOk;
  final String? apiMessage;
  final VoidCallback? onClearCache;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => _ExecuteCubit(getIt<ExecuteRepository>())..boot(),
      child: _ExecuteBarView(
        apiOk: apiOk,
        apiMessage: apiMessage,
        onClearCache: onClearCache,
      ),
    );
  }
}

