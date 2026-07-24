import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'swagger_embed_stub.dart'
    if (dart.library.html) 'swagger_embed_web.dart' as impl;

/// In-widget Swagger UI (Flutter web). Non-web shows a fallback message.
class SwaggerEmbed extends StatelessWidget {
  const SwaggerEmbed({
    super.key,
    required this.spec,
    required this.service,
    required this.environment,
    required this.tryBase,
    this.specRevision = '',
    this.token,
    this.onUseInTest,
    this.onRefresh,
    this.onHostReady,
  });

  final Map<String, dynamic> spec;
  final String service;
  final String environment;
  final String tryBase;
  final String specRevision;
  final String? token;
  final void Function(Map<String, dynamic> draft)? onUseInTest;
  final VoidCallback? onRefresh;
  final VoidCallback? onHostReady;

  @override
  Widget build(BuildContext context) {
    if (!kIsWeb) {
      return const Center(
        child: Text('Swagger UI embed is available on Flutter web.'),
      );
    }
    if (spec.isEmpty || !spec.containsKey('paths')) {
      return const Center(
        child: Text('No OpenAPI document loaded for this service.'),
      );
    }
    return impl.SwaggerEmbedView(
      spec: spec,
      service: service,
      environment: environment,
      tryBase: tryBase,
      specRevision: specRevision,
      token: token,
      onUseInTest: onUseInTest,
      onRefresh: onRefresh,
      onHostReady: onHostReady,
    );
  }
}
