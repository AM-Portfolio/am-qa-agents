part of 'flow_node_compose_card.dart';

class _PayloadOpt {
  const _PayloadOpt({
    required this.apiId,
    required this.name,
    required this.method,
    required this.path,
    required this.request,
    this.bodyOverride,
    this.headers,
  });

  final String apiId;
  final String name;
  final String method;
  final String path;
  final Map<String, dynamic> request;
  final Map<String, dynamic>? bodyOverride;
  final Map<String, dynamic>? headers;

  @override
  bool operator ==(Object other) =>
      other is _PayloadOpt && other.apiId == apiId && other.name == name;

  @override
  int get hashCode => Object.hash(apiId, name);
}
