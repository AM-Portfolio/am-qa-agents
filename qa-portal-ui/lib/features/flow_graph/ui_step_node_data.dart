class UiStepNodeData {
  const UiStepNodeData({
    required this.id,
    required this.label,
    this.kind = 'ui_step',
    this.method = 'STEP',
    this.status,
    this.durationMs,
    this.screenshotUrl,
    this.requestPeek,
    this.responsePeek,
    this.selected = false,
  });

  final String id;
  final String label;
  final String kind;
  final String method;
  final String? status;
  final double? durationMs;
  final String? screenshotUrl;
  final String? requestPeek;
  final String? responsePeek;
  final bool selected;

  bool get isManualTrigger =>
      kind == 'manual_trigger' || id == '__manual_trigger__';

  bool get isVerification => kind == 'verification';

  UiStepNodeData copyWith({
    String? status,
    double? durationMs,
    String? screenshotUrl,
    String? requestPeek,
    String? responsePeek,
    bool? selected,
    bool clearEvidence = false,
  }) {
    return UiStepNodeData(
      id: id,
      label: label,
      kind: kind,
      method: method,
      status: clearEvidence ? null : (status ?? this.status),
      durationMs: clearEvidence ? null : (durationMs ?? this.durationMs),
      screenshotUrl:
          clearEvidence ? null : (screenshotUrl ?? this.screenshotUrl),
      requestPeek: clearEvidence ? null : (requestPeek ?? this.requestPeek),
      responsePeek: clearEvidence ? null : (responsePeek ?? this.responsePeek),
      selected: selected ?? this.selected,
    );
  }
}
