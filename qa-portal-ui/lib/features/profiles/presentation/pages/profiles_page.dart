import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/di/injection.dart';
import '../../data/profiles_repository.dart';

class ProfilesPage extends StatelessWidget {
  const ProfilesPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => _ProfilesCubit(getIt<ProfilesRepository>())..load(),
      child: const _ProfilesView(),
    );
  }
}

class _ProfilesState extends Equatable {
  const _ProfilesState({
    this.loading = false,
    this.items = const [],
    this.error,
  });

  final bool loading;
  final List<Map<String, dynamic>> items;
  final String? error;

  _ProfilesState copyWith({
    bool? loading,
    List<Map<String, dynamic>>? items,
    String? error,
  }) {
    return _ProfilesState(
      loading: loading ?? this.loading,
      items: items ?? this.items,
      error: error,
    );
  }

  @override
  List<Object?> get props => [loading, items, error];
}

class _ProfilesCubit extends Cubit<_ProfilesState> {
  _ProfilesCubit(this._repo) : super(const _ProfilesState());

  final ProfilesRepository _repo;

  Future<void> load() async {
    emit(state.copyWith(loading: true, error: null));
    try {
      final items = await _repo.listConfigs();
      emit(state.copyWith(loading: false, items: items));
    } catch (e) {
      emit(state.copyWith(loading: false, error: e.toString()));
    }
  }
}

class _ProfilesView extends StatelessWidget {
  const _ProfilesView();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Text('Profiles', style: Theme.of(context).textTheme.headlineSmall),
              const Spacer(),
              FilledButton.icon(
                onPressed: () => context.read<_ProfilesCubit>().load(),
                icon: const Icon(Icons.refresh, size: 18),
                label: const Text('Refresh'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Expanded(
            child: BlocBuilder<_ProfilesCubit, _ProfilesState>(
              builder: (context, state) {
                if (state.loading && state.items.isEmpty) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (state.error != null && state.items.isEmpty) {
                  return Center(child: Text(state.error!));
                }
                if (state.items.isEmpty) {
                  return const Center(child: Text('No profiles yet.'));
                }
                return ListView.separated(
                  itemCount: state.items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final c = state.items[i];
                    return ListTile(
                      title: Text('${c['name'] ?? c['id'] ?? ''}'),
                      subtitle: Text(
                        '${c['service'] ?? ''} · ${c['environment'] ?? ''} · '
                        '${c['test_type'] ?? ''}',
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
