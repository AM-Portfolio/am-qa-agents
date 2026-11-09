import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../specs/data/specs_repository.dart';

class DatasetServiceRow {
  const DatasetServiceRow({
    required this.service,
    required this.label,
    required this.activeVersion,
    required this.sets,
    this.error,
  });

  final String service;
  final String label;
  final int? activeVersion;
  final List<Map<String, dynamic>> sets;
  final String? error;

  int get versionCount => sets.length;
}

class DatasetsState {
  const DatasetsState({
    this.loading = false,
    this.rows = const [],
    this.filter = '',
    this.activeOnly = false,
    this.message,
    this.busyService,
  });

  final bool loading;
  final List<DatasetServiceRow> rows;
  final String filter;
  final bool activeOnly;
  final String? message;
  final String? busyService;

  List<DatasetServiceRow> get visible {
    final q = filter.trim().toLowerCase();
    return [
      for (final r in rows)
        if ((!activeOnly || r.activeVersion != null) &&
            (q.isEmpty ||
                r.service.toLowerCase().contains(q) ||
                r.label.toLowerCase().contains(q)))
          r,
    ];
  }

  DatasetsState copyWith({
    bool? loading,
    List<DatasetServiceRow>? rows,
    String? filter,
    bool? activeOnly,
    String? message,
    String? busyService,
    bool clearMessage = false,
    bool clearBusy = false,
  }) {
    return DatasetsState(
      loading: loading ?? this.loading,
      rows: rows ?? this.rows,
      filter: filter ?? this.filter,
      activeOnly: activeOnly ?? this.activeOnly,
      message: clearMessage ? null : (message ?? this.message),
      busyService: clearBusy ? null : (busyService ?? this.busyService),
    );
  }
}

class DatasetsCubit extends Cubit<DatasetsState> {
  DatasetsCubit(this._repo) : super(const DatasetsState());

  final SpecsRepository _repo;

  Future<void> load() async {
    emit(state.copyWith(loading: true, clearMessage: true));
    try {
      final listed = await _repo.listServices();
      final rows = <DatasetServiceRow>[];
      for (final id in listed.ids) {
        try {
          final res = await _repo.catalogServicePayloadSets(id);
          rows.add(
            DatasetServiceRow(
              service: id,
              label: listed.labels[id] ?? id,
              activeVersion: res.activeVersion,
              sets: res.sets,
            ),
          );
        } catch (e) {
          rows.add(
            DatasetServiceRow(
              service: id,
              label: listed.labels[id] ?? id,
              activeVersion: null,
              sets: const [],
              error: '$e',
            ),
          );
        }
      }
      emit(state.copyWith(loading: false, rows: rows));
    } catch (e) {
      emit(
        state.copyWith(
          loading: false,
          message: 'Failed to load catalog: $e',
        ),
      );
    }
  }

  void setFilter(String q) => emit(state.copyWith(filter: q));

  void setActiveOnly(bool v) => emit(state.copyWith(activeOnly: v));

  Future<void> ensure(String service) async {
    emit(state.copyWith(busyService: service, clearMessage: true));
    try {
      await _repo.ensurePayloadSet(service);
      await load();
      emit(state.copyWith(message: 'Ensured working set for $service', clearBusy: true));
    } catch (e) {
      emit(state.copyWith(message: 'Ensure failed: $e', clearBusy: true));
    }
  }

  Future<void> activate(String service, String version) async {
    emit(state.copyWith(busyService: service, clearMessage: true));
    try {
      await _repo.activatePayloadSet(service, version);
      await load();
      emit(
        state.copyWith(
          message: 'Activated $service v$version',
          clearBusy: true,
        ),
      );
    } catch (e) {
      emit(state.copyWith(message: 'Activate failed: $e', clearBusy: true));
    }
  }
}
