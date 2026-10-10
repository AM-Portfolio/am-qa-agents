import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../execute/data/execute_repository.dart';
import '../../../flow_graph/graph_layout.dart';
import '../../../runs/data/runs_repository.dart';
import '../../data/ui_flows_repository.dart';
import 'ui_flows_state.dart';

part 'ui_flows_cubit_edit.part.dart';
part 'ui_flows_cubit_run.part.dart';

final _flowIdPattern = RegExp(r'^[A-Z0-9_]+$');

class UiFlowsCubit extends Cubit<UiFlowsState> {
  UiFlowsCubit(this._repo, this._execute, this._runs)
      : super(const UiFlowsState());

  final UiFlowsRepository _repo;
  final ExecuteRepository _execute;
  final RunsRepository _runs;
  Timer? _poll;

  @override
  Future<void> close() {
    _poll?.cancel();
    return super.close();
  }
}
