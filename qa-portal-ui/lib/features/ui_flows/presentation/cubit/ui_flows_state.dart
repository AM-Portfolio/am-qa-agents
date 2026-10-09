import 'package:equatable/equatable.dart';

class UiFlowsState extends Equatable {
  const UiFlowsState({
    this.loading = false,
    this.saving = false,
    this.running = false,
    this.agentOnline = false,
    this.agentUrl,
    this.error,
    this.flows = const [],
    this.suites = const [],
    this.selectedFlowId,
    this.graph,
    this.graphDirty = false,
    this.selectedNodeId,
    this.runId,
    this.runStatus,
    this.runSummary,
    this.runError,
    this.runTraceId,
    this.runCorrelationId,
    this.observabilityResources,
    this.traces = const [],
    this.evidenceByNodeId = const {},
    this.bottomTab = 0,
  });

  final bool loading;
  final bool saving;
  final bool running;
  final bool agentOnline;
  final String? agentUrl;
  final String? error;
  final List<Map<String, dynamic>> flows;
  final List<Map<String, dynamic>> suites;
  final String? selectedFlowId;
  final Map<String, dynamic>? graph;
  final bool graphDirty;
  final String? selectedNodeId;
  final String? runId;
  final String? runStatus;
  final String? runSummary;
  final String? runError;
  final String? runTraceId;
  final String? runCorrelationId;
  final Map<String, dynamic>? observabilityResources;
  final List<Map<String, dynamic>> traces;
  final Map<String, Map<String, dynamic>> evidenceByNodeId;
  final int bottomTab;

  Map<String, dynamic>? get selectedFlow {
    final id = selectedFlowId;
    if (id == null) return null;
    for (final f in flows) {
      if ('${f['id']}' == id) return f;
    }
    return null;
  }

  Map<String, dynamic>? get selectedEvidence {
    final id = selectedNodeId;
    if (id == null) return null;
    return evidenceByNodeId[id];
  }

  UiFlowsState copyWith({
    bool? loading,
    bool? saving,
    bool? running,
    bool? agentOnline,
    String? agentUrl,
    String? error,
    List<Map<String, dynamic>>? flows,
    List<Map<String, dynamic>>? suites,
    String? selectedFlowId,
    Map<String, dynamic>? graph,
    bool? graphDirty,
    String? selectedNodeId,
    String? runId,
    String? runStatus,
    String? runSummary,
    String? runError,
    String? runTraceId,
    String? runCorrelationId,
    Map<String, dynamic>? observabilityResources,
    List<Map<String, dynamic>>? traces,
    Map<String, Map<String, dynamic>>? evidenceByNodeId,
    int? bottomTab,
    bool clearError = false,
    bool clearGraph = false,
    bool clearSelectedNode = false,
    bool clearRun = false,
  }) {
    return UiFlowsState(
      loading: loading ?? this.loading,
      saving: saving ?? this.saving,
      running: running ?? this.running,
      agentOnline: agentOnline ?? this.agentOnline,
      agentUrl: agentUrl ?? this.agentUrl,
      error: clearError ? null : (error ?? this.error),
      flows: flows ?? this.flows,
      suites: suites ?? this.suites,
      selectedFlowId: selectedFlowId ?? this.selectedFlowId,
      graph: clearGraph ? null : (graph ?? this.graph),
      graphDirty: graphDirty ?? this.graphDirty,
      selectedNodeId:
          clearSelectedNode ? null : (selectedNodeId ?? this.selectedNodeId),
      runId: runId ?? (clearRun ? null : this.runId),
      runStatus: runStatus ?? (clearRun ? null : this.runStatus),
      runSummary: runSummary ?? (clearRun ? null : this.runSummary),
      runError: runError ?? (clearRun ? null : this.runError),
      runTraceId: runTraceId ?? (clearRun ? null : this.runTraceId),
      runCorrelationId:
          runCorrelationId ?? (clearRun ? null : this.runCorrelationId),
      observabilityResources: observabilityResources ??
          (clearRun ? null : this.observabilityResources),
      traces: traces ?? (clearRun ? const [] : this.traces),
      evidenceByNodeId:
          evidenceByNodeId ?? (clearRun ? const {} : this.evidenceByNodeId),
      bottomTab: bottomTab ?? this.bottomTab,
    );
  }

  @override
  List<Object?> get props => [
        loading,
        saving,
        running,
        agentOnline,
        agentUrl,
        error,
        flows,
        suites,
        selectedFlowId,
        graph,
        graphDirty,
        selectedNodeId,
        runId,
        runStatus,
        runSummary,
        runError,
        runTraceId,
        runCorrelationId,
        observabilityResources,
        traces,
        evidenceByNodeId,
        bottomTab,
      ];
}
