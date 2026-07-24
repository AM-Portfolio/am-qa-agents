// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:async';
import 'dart:convert';
import 'dart:html' as html;
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';

class SwaggerEmbedView extends StatefulWidget {
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
  State<SwaggerEmbedView> createState() => _SwaggerEmbedViewState();
}

class _SwaggerEmbedViewState extends State<SwaggerEmbedView> {
  static int _seq = 0;
  late final String _viewType;
  html.IFrameElement? _iframe;
  StreamSubscription<html.MessageEvent>? _sub;
  bool _hostReady = false;
  bool _mountedOnce = false;
  String? _lastRevision;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _viewType = 'spt-swagger-${_seq++}';
    ui_web.platformViewRegistry.registerViewFactory(_viewType, (int id) {
      final iframe = html.IFrameElement()
        ..src = 'swagger-ui/host.html'
        ..style.border = 'none'
        ..style.width = '100%'
        ..style.height = '100%'
        ..style.display = 'block';
      _iframe = iframe;
      iframe.onLoad.listen((_) {
        _hostReady = true;
        _scheduleMount(force: true);
      });
      return iframe;
    });
    _sub = html.window.onMessage.listen(_onMessage);
  }

  @override
  void didUpdateWidget(covariant SwaggerEmbedView oldWidget) {
    super.didUpdateWidget(oldWidget);
    final changed = oldWidget.specRevision != widget.specRevision ||
        oldWidget.token != widget.token ||
        oldWidget.service != widget.service ||
        oldWidget.environment != widget.environment ||
        oldWidget.tryBase != widget.tryBase;
    if (changed) {
      _scheduleMount(force: true);
    }
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _sub?.cancel();
    super.dispose();
  }

  void _onMessage(html.MessageEvent ev) {
    final data = ev.data;
    if (data is! Map) return;
    if (data['source'] != 'spt-swagger') return;
    final type = '${data['type'] ?? ''}';
    if (type == 'hostReady') {
      _hostReady = true;
      widget.onHostReady?.call();
      _scheduleMount(force: !_mountedOnce);
    } else if (type == 'ready') {
      _mountedOnce = true;
      // Do not remount — ready means Swagger finished; remounting caused blank UI.
    } else if (type == 'useInTest') {
      final draft = data['draft'];
      if (draft is Map) {
        widget.onUseInTest?.call(Map<String, dynamic>.from(draft));
      }
    } else if (type == 'refresh') {
      widget.onRefresh?.call();
    } else if (type == 'error') {
      // ignore
    }
  }

  void _scheduleMount({bool force = false}) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 80), () {
      _postMount(force: force);
    });
  }

  void _postMount({bool force = false}) {
    final win = _iframe?.contentWindow;
    if (win == null || !_hostReady) return;
    final rev = widget.specRevision.isEmpty
        ? '${widget.service}|${widget.environment}|${widget.spec.length}'
        : widget.specRevision;
    if (!force && _lastRevision == rev && _mountedOnce) return;
    _lastRevision = rev;

    final msg = <String, dynamic>{
      'source': 'spt-flutter',
      'type': 'mount',
      'spec': widget.spec,
      'token': widget.token,
      'tryBase': widget.tryBase,
      'service': widget.service,
      'environment': widget.environment,
    };
    win.postMessage(jsonDecode(jsonEncode(msg)), '*');
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox.expand(
      child: HtmlElementView(viewType: _viewType),
    );
  }
}
