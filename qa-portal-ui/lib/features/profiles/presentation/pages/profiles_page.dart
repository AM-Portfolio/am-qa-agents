import 'package:am_design_system/am_design_system.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/di/injection.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/json_lists.dart';
import '../../../execute/data/execute_repository.dart';
import '../../../specs/presentation/cubit/specs_profile_defaults.dart';
import '../../data/profiles_repository.dart';

part 'profiles_state_cubit.part.dart';
part 'profiles_view.part.dart';
part 'profiles_hover.part.dart';

const _durationPresets = ['30s', '1m', '5m', '10m'];

class ProfilesPage extends StatelessWidget {
  const ProfilesPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => ProfilesCubit(
        getIt<ProfilesRepository>(),
        getIt<ExecuteRepository>(),
        getIt<ApiClient>(),
      )..load(),
      child: const _ProfilesView(),
    );
  }
}

