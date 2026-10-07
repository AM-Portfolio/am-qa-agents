import 'package:equatable/equatable.dart';

class FlowsState extends Equatable {
  const FlowsState({
    this.loading = false,
    this.error,
    this.flows = const [],
    this.credentials = const [],
    this.selectedFlowId,
    this.graph,
    this.credentialId,
    this.env = 'prod',
    this.executionId,
    this.execution,
    this.executing = false,
    this.selectedLogNodeId,
    this.runtime,
    this.bottomTab = 0,
    this.recentExecutions = const [],
    this.execFilterStatus = '',
    this.execFilterFlowId = '',
    this.execFilterEnv = '',
    this.graphDirty = false,
    this.nodeQuickResults = const {},
  });

  final bool loading;
  final String? error;
  final List<Map<String, dynamic>> flows;
  final List<Map<String, dynamic>> credentials;
  final String? selectedFlowId;
  final Map<String, dynamic>? graph;
  final String? credentialId;
  final String env;
  final String? executionId;
  final Map<String, dynamic>? execution;
  final bool executing;
  final String? selectedLogNodeId;
  final Map<String, dynamic>? runtime;
  /// 0 = Run logs, 1 = Variables
  final int bottomTab;
  final List<Map<String, dynamic>> recentExecutions;
  final String execFilterStatus;
  final String execFilterFlowId;
  final String execFilterEnv;
  final bool graphDirty;
  final Map<String, Map<String, dynamic>> nodeQuickResults;

  FlowsState copyWith({
    bool? loading,
    String? error,
    List<Map<String, dynamic>>? flows,
    List<Map<String, dynamic>>? credentials,
    String? selectedFlowId,
    Map<String, dynamic>? graph,
    String? credentialId,
    String? env,
    String? executionId,
    Map<String, dynamic>? execution,
    bool? executing,
    String? selectedLogNodeId,
    Map<String, dynamic>? runtime,
    int? bottomTab,
    List<Map<String, dynamic>>? recentExecutions,
    String? execFilterStatus,
    String? execFilterFlowId,
    String? execFilterEnv,
    bool? graphDirty,
    Map<String, Map<String, dynamic>>? nodeQuickResults,
    bool clearError = false,
    bool clearExecution = false,
    bool clearCredentialId = false,
    bool clearRuntime = false,
    bool clearQuickResults = false,
  }) {
    return FlowsState(
      loading: loading ?? this.loading,
      error: clearError ? null : (error ?? this.error),
      flows: flows ?? this.flows,
      credentials: credentials ?? this.credentials,
      selectedFlowId: selectedFlowId ?? this.selectedFlowId,
      graph: graph ?? this.graph,
      credentialId: clearCredentialId
          ? null
          : (credentialId ?? this.credentialId),
      env: env ?? this.env,
      executionId: clearExecution ? null : (executionId ?? this.executionId),
      execution: clearExecution ? null : (execution ?? this.execution),
      executing: executing ?? this.executing,
      selectedLogNodeId: clearExecution
          ? null
          : (selectedLogNodeId ?? this.selectedLogNodeId),
      runtime: clearRuntime ? null : (runtime ?? this.runtime),
      bottomTab: bottomTab ?? this.bottomTab,
      recentExecutions: recentExecutions ?? this.recentExecutions,
      execFilterStatus: execFilterStatus ?? this.execFilterStatus,
      execFilterFlowId: execFilterFlowId ?? this.execFilterFlowId,
      execFilterEnv: execFilterEnv ?? this.execFilterEnv,
      graphDirty: graphDirty ?? this.graphDirty,
      nodeQuickResults: clearQuickResults
          ? const {}
          : (nodeQuickResults ?? this.nodeQuickResults),
    );
  }

  @override
  List<Object?> get props => [
        loading,
        error,
        flows,
        credentials,
        selectedFlowId,
        graph,
        credentialId,
        env,
        executionId,
        execution,
        executing,
        selectedLogNodeId,
        runtime,
        bottomTab,
        recentExecutions,
        execFilterStatus,
        execFilterFlowId,
        execFilterEnv,
        graphDirty,
        nodeQuickResults,
      ];
}

