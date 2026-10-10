import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/flows_repository.dart';
import '../utils/flows_errors.dart';
import 'flows_state.dart';

part 'flows_cubit_load.part.dart';
part 'flows_cubit_runtime.part.dart';
part 'flows_cubit_draft.part.dart';

class FlowsCubit extends Cubit<FlowsState> {
  FlowsCubit(this._repo) : super(const FlowsState());

  final FlowsRepository _repo;
  Timer? _poll;
  Timer? _queryDebounce;
  static const _pageSize = 100;

  @override
  Future<void> close() {
    _poll?.cancel();
    _queryDebounce?.cancel();
    return super.close();
  }
}
