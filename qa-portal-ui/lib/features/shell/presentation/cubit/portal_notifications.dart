import 'package:flutter_bloc/flutter_bloc.dart';

class PortalNotice {
  PortalNotice({
    required this.message,
    this.isError = true,
    DateTime? at,
  }) : at = at ?? DateTime.now();

  final String message;
  final bool isError;
  final DateTime at;
}

class PortalNotificationsState {
  const PortalNotificationsState({this.items = const []});

  final List<PortalNotice> items;

  int get unread => items.length;
}

/// In-memory notification bell for recent API / operator messages.
class PortalNotificationsCubit extends Cubit<PortalNotificationsState> {
  PortalNotificationsCubit() : super(const PortalNotificationsState());

  static const _cap = 30;

  void push(String message, {bool isError = true}) {
    final next = [
      PortalNotice(message: message, isError: isError),
      ...state.items,
    ];
    if (next.length > _cap) {
      next.removeRange(_cap, next.length);
    }
    emit(PortalNotificationsState(items: List.unmodifiable(next)));
  }

  void clear() => emit(const PortalNotificationsState());
}
