part of 'services_page.dart';

class ServicesState extends Equatable {
  const ServicesState({
    this.loading = false,
    this.overviewLoading = false,
    this.services = const [],
    this.serviceLabels = const {},
    this.railQuery = '',
    this.selectedService,
    this.environment = 'dev',
    this.overview,
    this.runStatusFilter = '',
    this.runQuery = '',
    this.error,
  });

  final bool loading;
  final bool overviewLoading;
  final List<String> services;
  final Map<String, String> serviceLabels;
  final String railQuery;
  final String? selectedService;
  final String environment;
  final Map<String, dynamic>? overview;
  final String runStatusFilter;
  final String runQuery;
  final String? error;

  String labelFor(String id) => serviceLabels[id] ?? id;

  List<String> get filteredServices {
    final q = railQuery.trim().toLowerCase();
    if (q.isEmpty) return services;
    return services
        .where(
          (id) =>
              id.toLowerCase().contains(q) ||
              labelFor(id).toLowerCase().contains(q),
        )
        .toList();
  }

  List<Map<String, dynamic>> get filteredRuns {
    final raw = overview?['runs'];
    final runs = mapList(raw);
    final status = runStatusFilter.trim().toLowerCase();
    final q = runQuery.trim().toLowerCase();
    return runs.where((r) {
      if (status.isNotEmpty &&
          '${r['status'] ?? ''}'.toLowerCase() != status) {
        return false;
      }
      if (q.isEmpty) return true;
      final hay =
          '${r['id']} ${r['triggered_by']} ${r['config_name']} ${r['status']}'
              .toLowerCase();
      return hay.contains(q);
    }).toList();
  }

  ServicesState copyWith({
    bool? loading,
    bool? overviewLoading,
    List<String>? services,
    Map<String, String>? serviceLabels,
    String? railQuery,
    String? selectedService,
    bool clearSelected = false,
    String? environment,
    Map<String, dynamic>? overview,
    bool clearOverview = false,
    String? runStatusFilter,
    String? runQuery,
    String? error,
    bool clearError = false,
  }) {
    return ServicesState(
      loading: loading ?? this.loading,
      overviewLoading: overviewLoading ?? this.overviewLoading,
      services: services ?? this.services,
      serviceLabels: serviceLabels ?? this.serviceLabels,
      railQuery: railQuery ?? this.railQuery,
      selectedService:
          clearSelected ? null : (selectedService ?? this.selectedService),
      environment: environment ?? this.environment,
      overview: clearOverview ? null : (overview ?? this.overview),
      runStatusFilter: runStatusFilter ?? this.runStatusFilter,
      runQuery: runQuery ?? this.runQuery,
      error: clearError ? null : (error ?? this.error),
    );
  }

  @override
  List<Object?> get props => [
        loading,
        overviewLoading,
        services,
        serviceLabels,
        railQuery,
        selectedService,
        environment,
        overview,
        runStatusFilter,
        runQuery,
        error,
      ];
}

class ServicesCubit extends Cubit<ServicesState> {
  ServicesCubit(this._repo) : super(const ServicesState());

  final ServicesRepository _repo;

  Future<void> boot({String? initialService}) async {
    emit(state.copyWith(loading: true, clearError: true));
    try {
      final listed = await _repo.listServices();
      final pick = (initialService != null &&
              listed.ids.contains(initialService))
          ? initialService
          : (listed.ids.isNotEmpty ? listed.ids.first : null);
      emit(
        state.copyWith(
          loading: false,
          services: listed.ids,
          serviceLabels: listed.labels,
          selectedService: pick,
        ),
      );
      if (pick != null) {
        await selectService(pick);
      }
    } catch (e) {
      emit(state.copyWith(loading: false, error: '$e'));
    }
  }

  void setRailQuery(String q) => emit(state.copyWith(railQuery: q));

  void setRunStatusFilter(String v) =>
      emit(state.copyWith(runStatusFilter: v));

  void setRunQuery(String q) => emit(state.copyWith(runQuery: q));

  Future<void> setEnvironment(String env) async {
    emit(state.copyWith(environment: env));
    final svc = state.selectedService;
    if (svc != null) await selectService(svc);
  }

  Future<void> selectService(String serviceId) async {
    emit(
      state.copyWith(
        selectedService: serviceId,
        overviewLoading: true,
        clearError: true,
        clearOverview: true,
        runStatusFilter: '',
        runQuery: '',
      ),
    );
    try {
      final ov = await _repo.overview(
        serviceId,
        environment: state.environment,
      );
      emit(state.copyWith(overviewLoading: false, overview: ov));
    } catch (e) {
      emit(state.copyWith(overviewLoading: false, error: '$e'));
    }
  }

  Future<void> refresh() async {
    final svc = state.selectedService;
    if (svc == null) {
      await boot();
      return;
    }
    await selectService(svc);
  }
}

