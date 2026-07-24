import 'package:am_design_system/am_design_system.dart';
import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';

import '../config/portal_config.dart';
import '../network/api_client.dart';
import '../../features/runs/data/runs_repository.dart';
import '../../features/profiles/data/profiles_repository.dart';
import '../../features/execute/data/execute_repository.dart';
import '../../features/specs/data/specs_repository.dart';
import '../../features/ui_flows/data/ui_flows_repository.dart';

final getIt = GetIt.instance;

Future<void> configureDependencies() async {
  if (!getIt.isRegistered<PortalConfig>()) {
    getIt.registerSingleton<PortalConfig>(PortalConfig.fromEnvironment());
  }

  if (!getIt.isRegistered<ThemeRepository>()) {
    getIt.registerLazySingleton<ThemeRepository>(() => ThemeRepository());
  }
  if (!getIt.isRegistered<ThemeCubit>()) {
    getIt.registerLazySingleton<ThemeCubit>(
      () => ThemeCubit(getIt<ThemeRepository>()),
    );
  }

  if (!getIt.isRegistered<Dio>()) {
    getIt.registerLazySingleton<Dio>(() {
      final cfg = getIt<PortalConfig>();
      return Dio(
        BaseOptions(
          baseUrl: cfg.apiBase,
          connectTimeout: const Duration(seconds: 20),
          receiveTimeout: const Duration(seconds: 60),
          headers: {'Accept': 'application/json'},
        ),
      );
    });
  }

  if (!getIt.isRegistered<ApiClient>()) {
    getIt.registerLazySingleton<ApiClient>(() => ApiClient(getIt<Dio>()));
  }
  if (!getIt.isRegistered<RunsRepository>()) {
    getIt.registerLazySingleton<RunsRepository>(
      () => RunsRepository(getIt<ApiClient>()),
    );
  }
  if (!getIt.isRegistered<ProfilesRepository>()) {
    getIt.registerLazySingleton<ProfilesRepository>(
      () => ProfilesRepository(getIt<ApiClient>()),
    );
  }
  if (!getIt.isRegistered<ExecuteRepository>()) {
    getIt.registerLazySingleton<ExecuteRepository>(
      () => ExecuteRepository(getIt<ApiClient>()),
    );
  }
  if (!getIt.isRegistered<SpecsRepository>()) {
    getIt.registerLazySingleton<SpecsRepository>(
      () => SpecsRepository(getIt<ApiClient>()),
    );
  }
  if (!getIt.isRegistered<UiFlowsRepository>()) {
    getIt.registerLazySingleton<UiFlowsRepository>(
      () => UiFlowsRepository(getIt<ApiClient>()),
    );
  }
}
