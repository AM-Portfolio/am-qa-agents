import 'package:am_design_system/am_design_system.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/di/injection.dart';
import '../../../../core/network/json_lists.dart';
import '../../../../core/router/app_router.dart';
import '../../../execute/data/execute_repository.dart';
import '../../data/services_repository.dart';
import '../widgets/coverage_board.dart';

part 'services_state_cubit.part.dart';
part 'services_view.part.dart';
part 'services_overview.part.dart';

class ServicesPage extends StatelessWidget {
  const ServicesPage({super.key, this.initialService});

  final String? initialService;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => ServicesCubit(getIt<ServicesRepository>())
        ..boot(initialService: initialService),
      child: const _ServicesView(),
    );
  }
}

