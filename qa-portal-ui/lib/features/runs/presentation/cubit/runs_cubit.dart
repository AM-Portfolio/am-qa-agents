import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/runs_repository.dart';

class RunsState extends Equatable {
  const RunsState({
    this.loading = false,
    this.items = const [],
    this.total = 0,
    this.offset = 0,
    this.status = '',
    this.service = '',
    this.environment = '',
    this.testType = '',
    this.from = '',
    this.to = '',
    this.q = '',
    this.error,
  });

  static const pageSize = 20;

  final bool loading;
  final List<Map<String, dynamic>> items;
  final int total;
  final int offset;
  final String status;
  final String service;
  final String environment;
  final String testType;
  final String from;
  final String to;
  final String q;
  final String? error;

  bool get hasPrev => offset > 0;
  bool get hasNext => offset + items.length < total;

  RunsState copyWith({
    bool? loading,
    List<Map<String, dynamic>>? items,
    int? total,
    int? offset,
    String? status,
    String? service,
    String? environment,
    String? testType,
    String? from,
    String? to,
    String? q,
    String? error,
  }) {
    return RunsState(
      loading: loading ?? this.loading,
      items: items ?? this.items,
      total: total ?? this.total,
      offset: offset ?? this.offset,
      status: status ?? this.status,
      service: service ?? this.service,
      environment: environment ?? this.environment,
      testType: testType ?? this.testType,
      from: from ?? this.from,
      to: to ?? this.to,
      q: q ?? this.q,
      error: error,
    );
  }

  @override
  List<Object?> get props => [
        loading,
        items,
        total,
        offset,
        status,
        service,
        environment,
        testType,
        from,
        to,
        q,
        error,
      ];
}

class RunsCubit extends Cubit<RunsState> {
  RunsCubit(this._repo) : super(const RunsState());

  final RunsRepository _repo;

  void setStatus(String v) => emit(state.copyWith(status: v, offset: 0));
  void setService(String v) => emit(state.copyWith(service: v, offset: 0));
  void setEnvironment(String v) => emit(state.copyWith(environment: v, offset: 0));
  void setTestType(String v) => emit(state.copyWith(testType: v, offset: 0));
  void setFrom(String v) => emit(state.copyWith(from: v, offset: 0));
  void setTo(String v) => emit(state.copyWith(to: v, offset: 0));
  void setQ(String v) => emit(state.copyWith(q: v, offset: 0));

  Future<void> nextPage() async {
    if (!state.hasNext) return;
    emit(state.copyWith(offset: state.offset + RunsState.pageSize));
    await load();
  }

  Future<void> prevPage() async {
    if (!state.hasPrev) return;
    final next = state.offset - RunsState.pageSize;
    emit(state.copyWith(offset: next < 0 ? 0 : next));
    await load();
  }

  Future<void> load() async {
    emit(state.copyWith(loading: true, error: null));
    try {
      final result = await _repo.listRuns(
        status: state.status.isEmpty ? null : state.status,
        service: state.service.isEmpty ? null : state.service,
        environment: state.environment.isEmpty ? null : state.environment,
        testType: state.testType.isEmpty ? null : state.testType,
        from: state.from.isEmpty ? null : state.from,
        to: state.to.isEmpty ? null : state.to,
        q: state.q.isEmpty ? null : state.q,
        limit: RunsState.pageSize,
        offset: state.offset,
      );
      emit(
        state.copyWith(
          loading: false,
          items: result.runs,
          total: result.total,
        ),
      );
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }
}
