import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/config/portal_config.dart';
import '../../../../core/di/injection.dart';
import '../cubit/specs_cubit.dart';
import '../widgets/swagger_embed.dart';

class SpecsSwaggerTab extends StatelessWidget {
  const SpecsSwaggerTab({super.key, this.onUseInTest});

  final VoidCallback? onUseInTest;

  String _tryBase() {
    final cfg = getIt<PortalConfig>();
    return cfg.apiBase.replaceAll(RegExp(r'/$'), '');
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<SpecsCubit, SpecsState>(
      buildWhen: (p, c) =>
          p.openapiDoc != c.openapiDoc ||
          p.specRevision != c.specRevision ||
          p.selectedPayloadVersion != c.selectedPayloadVersion ||
          p.generateResults != c.generateResults ||
          p.loading != c.loading ||
          p.selectedService != c.selectedService ||
          p.environment != c.environment ||
          p.tryToken != c.tryToken,
      builder: (context, state) {
        final svc = state.selectedService;
        if (svc == null) {
          return const Center(child: Text('Select a workspace service'));
        }
        final cubit = context.read<SpecsCubit>();
        final doc = cubit.swaggerSpecWithPayloadExamples() ?? state.openapiDoc;
        if (doc == null) {
          return Center(
            child: Text(
              state.loading
                  ? 'Loading OpenAPI…'
                  : 'No OpenAPI document for $svc.',
            ),
          );
        }
        return SwaggerEmbed(
          key: ValueKey(state.specRevision),
          spec: doc,
          specRevision: state.specRevision,
          service: svc,
          environment: state.environment,
          tryBase: _tryBase(),
          token: state.tryToken,
          onRefresh: () => cubit.selectService(svc),
          onUseInTest: (draft) {
            cubit.applyPayloadMap(draft);
            onUseInTest?.call();
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Applied to Test')),
            );
          },
        );
      },
    );
  }
}
