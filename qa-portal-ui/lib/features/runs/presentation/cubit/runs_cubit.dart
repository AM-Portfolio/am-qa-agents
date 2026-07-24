import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/runs_repository.dart';

class RunsState extends Equatable {
  const RunsState({
    this.loading = false,
    this.items = const [],
    this.error,
  });

  final bool loading;
  final List<Map<String, dynamic>> items;
  final String? error;

  RunsState copyWith({
    bool? loading,
    List<Map<String, dynamic>>? items,
    String? error,
  }) {
    return RunsState(
      loading: loading ?? this.loading,
      items: items ?? this.items,
      error: error,
    );
  }

  @override
  List<Object?> get props => [loading, items, error];
}

class RunsCubit extends Cubit<RunsState> {
  RunsCubit(this._repo) : super(const RunsState());

  final RunsRepository _repo;

  Future<void> load() async {
    emit(state.copyWith(loading: true, error: null));
    try {
      final items = await _repo.listRuns();
      emit(state.copyWith(loading: false, items: items));
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }
}
