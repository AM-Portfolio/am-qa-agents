import 'package:flutter/material.dart';

class SwaggerEmbedView extends StatelessWidget {
  const SwaggerEmbedView({
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
    return const Center(child: Text('Swagger UI requires Flutter web.'));
  }
}
