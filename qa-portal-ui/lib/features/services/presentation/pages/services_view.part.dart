part of 'services_page.dart';

class _ServicesView extends StatelessWidget {
  const _ServicesView();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            width: 260,
            child: GlassCard(
              padding: const EdgeInsets.all(12),
              child: BlocBuilder<ServicesCubit, ServicesState>(
                builder: (context, state) {
                  final cubit = context.read<ServicesCubit>();
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        'Services',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        decoration: const InputDecoration(
                          isDense: true,
                          hintText: 'Search catalog…',
                          prefixIcon: Icon(Icons.search, size: 18),
                        ),
                        onChanged: cubit.setRailQuery,
                      ),
                      const SizedBox(height: 8),
                      DropdownButtonFormField<String>(
                        key: ValueKey('env-${state.environment}'),
                        initialValue: state.environment,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          isDense: true,
                          labelText: 'Environment',
                        ),
                        items: const [
                          DropdownMenuItem(value: 'dev', child: Text('dev')),
                          DropdownMenuItem(
                            value: 'preprod',
                            child: Text('preprod'),
                          ),
                          DropdownMenuItem(value: 'prod', child: Text('prod')),
                        ],
                        onChanged: (v) {
                          if (v != null) cubit.setEnvironment(v);
                        },
                      ),
                      const SizedBox(height: 8),
                      Chip(
                        visualDensity: VisualDensity.compact,
                        label: Text('${state.filteredServices.length} services'),
                      ),
                      const SizedBox(height: 8),
                      if (state.loading)
                        const Expanded(
                          child: Center(child: CircularProgressIndicator()),
                        )
                      else
                        Expanded(
                          child: ListView.builder(
                            itemCount: state.filteredServices.length,
                            itemBuilder: (context, i) {
                              final id = state.filteredServices[i];
                              final selected = id == state.selectedService;
                              return ListTile(
                                dense: true,
                                selected: selected,
                                title: Text(
                                  state.labelFor(id),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                subtitle: Text(
                                  id,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                                onTap: () {
                                  context.go('${AppRoutes.services}/$id');
                                  cubit.selectService(id);
                                },
                              );
                            },
                          ),
                        ),
                    ],
                  );
                },
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: BlocBuilder<ServicesCubit, ServicesState>(
              builder: (context, state) {
                if (state.error != null && state.overview == null) {
                  return GlassCard(
                    child: Center(child: Text(state.error!)),
                  );
                }
                if (state.overviewLoading && state.overview == null) {
                  return const GlassCard(
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                if (state.selectedService == null) {
                  return const GlassCard(
                    child: Center(child: Text('Select a service')),
                  );
                }
                return _OverviewBody(state: state);
              },
            ),
          ),
        ],
      ),
    );
  }
}

