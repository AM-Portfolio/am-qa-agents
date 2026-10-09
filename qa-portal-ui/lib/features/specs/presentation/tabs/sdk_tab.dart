import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:url_launcher/url_launcher.dart';

import '../cubit/specs_cubit.dart';

/// SDK surface over existing APIs / MCP tools / openapiUrl — no codegen backend.
class SpecsSdkTab extends StatelessWidget {
  const SpecsSdkTab({super.key, required this.state});

  final SpecsState state;

  Future<void> _openUrl(String? url) async {
    final u = (url ?? '').trim();
    if (u.isEmpty) return;
    final uri = Uri.tryParse(u);
    if (uri == null) return;
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<SpecsCubit>();
    final openapiUrl = state.openapiUrl;
    final target = state.targetUrl;
    final ops = state.operationCount ?? state.apis.length;
    final tools = state.toolsCount ?? state.mcpTools.length;

    return Padding(
      padding: const EdgeInsets.all(16),
      child: ListView(
        children: [
          Text(
            'SDK & client stubs',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            'Generate clients from the live OpenAPI URL and MCP tool list. '
            'No portal codegen service — copy the URL into your preferred generator.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'OpenAPI source',
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                  const SizedBox(height: 8),
                  SelectableText(
                    openapiUrl?.isNotEmpty == true
                        ? openapiUrl!
                        : (state.selectedService == null
                            ? 'Select a collection first'
                            : 'OpenAPI URL not available yet — open Swagger tab to load the doc.'),
                    style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: [
                      FilledButton.tonal(
                        onPressed: openapiUrl == null || openapiUrl.isEmpty
                            ? null
                            : () {
                                Clipboard.setData(
                                  ClipboardData(text: openapiUrl),
                                );
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('OpenAPI URL copied'),
                                  ),
                                );
                              },
                        child: const Text('Copy URL'),
                      ),
                      TextButton(
                        onPressed: openapiUrl == null || openapiUrl.isEmpty
                            ? null
                            : () => _openUrl(openapiUrl),
                        child: const Text('Open'),
                      ),
                      TextButton(
                        onPressed: state.selectedService == null
                            ? null
                            : () => cubit.ensureOpenapiDoc(force: true),
                        child: state.openapiLoading
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('Refresh meta'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Surface inventory',
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                  const SizedBox(height: 8),
                  Text('Environment: ${state.environment}'),
                  if (target != null) Text('Target: $target'),
                  Text('REST operations: $ops'),
                  Text('MCP tools: $tools'),
                  const SizedBox(height: 8),
                  Text(
                    'Suggested generators: openapi-generator, fern, speakeasy, '
                    'or your language’s official OpenAPI client.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'APIs (${state.apis.length})',
            style: Theme.of(context).textTheme.labelLarge,
          ),
          const SizedBox(height: 4),
          if (state.apisLoading)
            const LinearProgressIndicator(minHeight: 2)
          else
            ...state.apis.take(40).map((api) {
              final m = '${api['method'] ?? 'GET'}'.toUpperCase();
              final p = '${api['path'] ?? api['url'] ?? ''}';
              return ListTile(
                dense: true,
                title: Text(
                  '$m $p',
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                ),
              );
            }),
          if (state.apis.length > 40)
            Text(
              '…and ${state.apis.length - 40} more',
              style: Theme.of(context).textTheme.labelSmall,
            ),
          const SizedBox(height: 12),
          Text(
            'MCP tools (${state.mcpTools.length})',
            style: Theme.of(context).textTheme.labelLarge,
          ),
          const SizedBox(height: 4),
          if (state.mcpLoading && state.mcpTools.isEmpty)
            const LinearProgressIndicator(minHeight: 2)
          else
            ...state.mcpTools.take(40).map((t) {
              final name = '${t['name'] ?? t['tool'] ?? ''}';
              return ListTile(
                dense: true,
                leading: const Icon(Icons.smart_toy_outlined, size: 16),
                title: Text(name, style: const TextStyle(fontSize: 12)),
              );
            }),
        ],
      ),
    );
  }
}
