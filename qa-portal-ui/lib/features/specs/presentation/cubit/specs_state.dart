import 'package:equatable/equatable.dart';

import '../../domain/try_draft.dart';

class SpecsState extends Equatable {
  const SpecsState({
    this.loading = false,
    this.services = const [],
    this.serviceLabels = const {},
    this.configs = const [],
    this.selectedService,
    this.environment = 'dev',
    this.apis = const [],
    this.openapi,
    this.openapiDoc,
    this.openapiUrl,
    this.targetUrl,
    this.specRevision = '',
    this.selectedApiId,
    this.selectedApiIds = const {},
    this.payloadSets = const [],
    this.selectedPayloadVersion,
    this.selectedPayloadApiIds = const {},
    this.draft = const TryDraft(),
    this.tryResult,
    this.tryStatusCode,
    this.tryDurationMs,
    this.actionResult,
    this.mcpSummary,
    this.mcpTools = const [],
    this.mcpToolReport,
    this.mcpRunning = false,
    this.selectedMcpToolNames = const {},
    this.operationCount,
    this.toolsCount,
    this.overview,
    this.overviewLoading = false,
    this.generateResults = const [],
    this.generateSummary,
    this.generating = false,
    this.onboarding = false,
    this.onboardWorkflowId,
    this.onboardReport,
    this.tryToken,
    this.canRevert = false,
    this.error,
    this.health,
    this.message,
    this.fileBytes = const {},
    this.lastPayloadDiff = const [],
    this.paramEnums = const {},
  });

  final bool loading;
  final List<String> services;
  final Map<String, String> serviceLabels;
  final List<Map<String, dynamic>> configs;
  final String? selectedService;
  final String environment;
  final List<Map<String, dynamic>> apis;
  final Map<String, dynamic>? openapi;
  /// Stable OpenAPI document reference (do not re-copy on every read).
  final Map<String, dynamic>? openapiDoc;
  final String? openapiUrl;
  /// Catalog service base URL for this env (shareable curl target).
  final String? targetUrl;
  /// Bumps only when Swagger should remount.
  final String specRevision;
  final String? selectedApiId;
  final Set<String> selectedApiIds;
  final List<Map<String, dynamic>> payloadSets;
  final String? selectedPayloadVersion;
  /// Multi-select of payload-set API ids on the Data tab.
  final Set<String> selectedPayloadApiIds;
  final TryDraft draft;
  final String? tryResult;
  final int? tryStatusCode;
  final int? tryDurationMs;
  final String? actionResult;
  final Map<String, dynamic>? mcpSummary;
  /// OpenAPI MCP tools (same ops as APIs / Swagger).
  final List<Map<String, dynamic>> mcpTools;
  final Map<String, dynamic>? mcpToolReport;
  final bool mcpRunning;
  final Set<String> selectedMcpToolNames;
  final int? operationCount;
  final int? toolsCount;
  final Map<String, dynamic>? overview;
  final bool overviewLoading;
  final List<Map<String, dynamic>> generateResults;
  final Map<String, dynamic>? generateSummary;
  final bool generating;
  final bool onboarding;
  final String? onboardWorkflowId;
  final Map<String, dynamic>? onboardReport;
  final String? tryToken;
  final bool canRevert;
  final String? error;
  final Map<String, dynamic>? health;
  final String? message;
  final Map<String, ({String name, List<int> bytes})> fileBytes;
  final List<DraftFieldChange> lastPayloadDiff;
  /// OpenAPI enum options for path/query/header param names.
  final Map<String, List<String>> paramEnums;

  bool get syncCountsMatch {
    final ops = operationCount ?? openapi?['operation_count'];
    final tools = toolsCount ?? mcpTools.length;
    if (ops is! num) return apis.length == tools;
    return apis.length == ops.toInt() && tools == ops.toInt();
  }

  String labelFor(String serviceId) => serviceLabels[serviceId] ?? serviceId;

  Map<String, dynamic>? get selectedApi {
    for (var i = 0; i < apis.length; i++) {
      final id = '${apis[i]['id'] ?? apis[i]['operationId'] ?? i}';
      if (id == selectedApiId) return apis[i];
    }
    return null;
  }

  Map<String, dynamic>? get openapiDocument => openapiDoc;

  SpecsState copyWith({
    bool? loading,
    List<String>? services,
    Map<String, String>? serviceLabels,
    List<Map<String, dynamic>>? configs,
    String? selectedService,
    String? environment,
    List<Map<String, dynamic>>? apis,
    Map<String, dynamic>? openapi,
    Map<String, dynamic>? openapiDoc,
    String? openapiUrl,
    String? targetUrl,
    String? specRevision,
    String? selectedApiId,
    Set<String>? selectedApiIds,
    List<Map<String, dynamic>>? payloadSets,
    String? selectedPayloadVersion,
    Set<String>? selectedPayloadApiIds,
    TryDraft? draft,
    String? tryResult,
    int? tryStatusCode,
    int? tryDurationMs,
    String? actionResult,
    Map<String, dynamic>? mcpSummary,
    List<Map<String, dynamic>>? mcpTools,
    Map<String, dynamic>? mcpToolReport,
    bool? mcpRunning,
    Set<String>? selectedMcpToolNames,
    int? operationCount,
    int? toolsCount,
    Map<String, dynamic>? overview,
    bool? overviewLoading,
    List<Map<String, dynamic>>? generateResults,
    Map<String, dynamic>? generateSummary,
    bool? generating,
    bool? onboarding,
    String? onboardWorkflowId,
    Map<String, dynamic>? onboardReport,
    String? tryToken,
    bool? canRevert,
    String? error,
    Map<String, dynamic>? health,
    String? message,
    Map<String, ({String name, List<int> bytes})>? fileBytes,
    List<DraftFieldChange>? lastPayloadDiff,
    Map<String, List<String>>? paramEnums,
    bool clearOpenapi = false,
    bool clearOpenapiUrl = false,
    bool clearTargetUrl = false,
    bool clearTryResult = false,
    bool clearActionResult = false,
    bool clearPayloadVersion = false,
    bool clearPayloadApiIds = false,
    bool clearMcpSummary = false,
    bool clearMcpReport = false,
    bool clearMcpTools = false,
    bool clearCounts = false,
    bool clearOverview = false,
    bool clearGenerate = false,
    bool clearOnboard = false,
    bool clearPayloadDiff = false,
    bool clearParamEnums = false,
    bool clearTryToken = false,
  }) {
    return SpecsState(
      loading: loading ?? this.loading,
      services: services ?? this.services,
      serviceLabels: serviceLabels ?? this.serviceLabels,
      configs: configs ?? this.configs,
      selectedService: selectedService ?? this.selectedService,
      environment: environment ?? this.environment,
      apis: apis ?? this.apis,
      openapi: clearOpenapi ? null : (openapi ?? this.openapi),
      openapiDoc: clearOpenapi ? null : (openapiDoc ?? this.openapiDoc),
      openapiUrl: clearOpenapiUrl ? null : (openapiUrl ?? this.openapiUrl),
      targetUrl: clearTargetUrl ? null : (targetUrl ?? this.targetUrl),
      specRevision: specRevision ?? this.specRevision,
      selectedApiId: selectedApiId ?? this.selectedApiId,
      selectedApiIds: selectedApiIds ?? this.selectedApiIds,
      payloadSets: payloadSets ?? this.payloadSets,
      selectedPayloadVersion: clearPayloadVersion
          ? null
          : (selectedPayloadVersion ?? this.selectedPayloadVersion),
      selectedPayloadApiIds: clearPayloadApiIds
          ? const {}
          : (selectedPayloadApiIds ?? this.selectedPayloadApiIds),
      draft: draft ?? this.draft,
      tryResult: clearTryResult ? null : (tryResult ?? this.tryResult),
      tryStatusCode: clearTryResult ? null : (tryStatusCode ?? this.tryStatusCode),
      tryDurationMs: clearTryResult ? null : (tryDurationMs ?? this.tryDurationMs),
      actionResult: clearActionResult ? null : (actionResult ?? this.actionResult),
      mcpSummary: clearMcpSummary ? null : (mcpSummary ?? this.mcpSummary),
      mcpTools: clearMcpTools ? const [] : (mcpTools ?? this.mcpTools),
      mcpToolReport: clearMcpReport ? null : (mcpToolReport ?? this.mcpToolReport),
      mcpRunning: mcpRunning ?? this.mcpRunning,
      selectedMcpToolNames:
          selectedMcpToolNames ?? this.selectedMcpToolNames,
      operationCount: clearCounts ? null : (operationCount ?? this.operationCount),
      toolsCount: clearCounts ? null : (toolsCount ?? this.toolsCount),
      overview: clearOverview ? null : (overview ?? this.overview),
      overviewLoading: overviewLoading ?? this.overviewLoading,
      generateResults:
          clearGenerate ? const [] : (generateResults ?? this.generateResults),
      generateSummary:
          clearGenerate ? null : (generateSummary ?? this.generateSummary),
      generating: generating ?? this.generating,
      onboarding: onboarding ?? this.onboarding,
      onboardWorkflowId: clearOnboard
          ? null
          : (onboardWorkflowId ?? this.onboardWorkflowId),
      onboardReport:
          clearOnboard ? null : (onboardReport ?? this.onboardReport),
      tryToken: clearTryToken ? null : (tryToken ?? this.tryToken),
      canRevert: canRevert ?? this.canRevert,
      error: error,
      health: health ?? this.health,
      message: message,
      fileBytes: fileBytes ?? this.fileBytes,
      lastPayloadDiff:
          clearPayloadDiff ? const [] : (lastPayloadDiff ?? this.lastPayloadDiff),
      paramEnums: clearParamEnums ? const {} : (paramEnums ?? this.paramEnums),
    );
  }

  @override
  List<Object?> get props => [
        loading,
        services,
        serviceLabels,
        configs,
        selectedService,
        environment,
        apis,
        openapi,
        openapiDoc,
        openapiUrl,
        targetUrl,
        specRevision,
        selectedApiId,
        selectedApiIds,
        payloadSets,
        selectedPayloadVersion,
        selectedPayloadApiIds,
        draft,
        tryResult,
        tryStatusCode,
        tryDurationMs,
        actionResult,
        mcpSummary,
        mcpTools,
        mcpToolReport,
        mcpRunning,
        selectedMcpToolNames,
        operationCount,
        toolsCount,
        overview,
        overviewLoading,
        generateResults,
        generateSummary,
        generating,
        onboarding,
        onboardWorkflowId,
        onboardReport,
        tryToken,
        canRevert,
        error,
        health,
        message,
        fileBytes.keys.toList(),
        lastPayloadDiff.length,
        paramEnums.keys.toList(),
      ];
}

