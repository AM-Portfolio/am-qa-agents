import 'dart:convert';

import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/config/portal_config.dart';
import '../../../../core/di/injection.dart';
import '../../../../core/router/app_router.dart';
import '../../../flow_graph/ui_step_flow_canvas.dart';
import '../../../observability/presentation/widgets/observability_attach.dart';
import '../../data/runs_repository.dart';
import '../utils/ui_run_graph.dart';

part 'run_detail_cubit.part.dart';
part 'run_detail_view.part.dart';
part 'run_detail_helpers.part.dart';
part 'run_detail_summary.part.dart';
part 'run_detail_baseline.part.dart';
part 'run_detail_trace_utils.part.dart';
part 'run_detail_inspector.part.dart';
part 'run_detail_trace_panel.part.dart';
part 'run_detail_tabs.part.dart';

class RunDetailPage extends StatelessWidget {
  const RunDetailPage({super.key, required this.runId});

  final String runId;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => _RunDetailCubit(getIt<RunsRepository>(), runId)..load(),
      child: _RunDetailView(runId: runId),
    );
  }
}
