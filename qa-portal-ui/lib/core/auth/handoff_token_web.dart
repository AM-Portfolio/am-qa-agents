import 'dart:html' as html;

const _sessionKey = 'am_qa_central_token';
const _handoffKey = 'am_qa_handoff_code';

String? _capturedToken;
String? _capturedHandoff;

/// Call from [main] before GoRouter starts so the URL is not wiped first.
void captureCentralHandoffTokenEarly() {
  _capturedToken = _readTokenFromBrowser();
  _capturedHandoff = _readHandoffFromBrowser();
  if (_capturedToken != null || _capturedHandoff != null) {
    _stripHandoffFromUrl();
  }
}

/// Read AM Central token stashed by Modern UI (early capture, storage, fragment, query).
String? readCentralHandoffToken() {
  if (_capturedToken != null && _capturedToken!.isNotEmpty) {
    return _capturedToken;
  }
  return _readTokenFromBrowser();
}

/// One-time mint code from Modern UI (`?handoff=`).
String? readCentralHandoffCode() {
  if (_capturedHandoff != null && _capturedHandoff!.isNotEmpty) {
    return _capturedHandoff;
  }
  return _readHandoffFromBrowser();
}

void clearCentralHandoffToken() {
  _capturedToken = null;
  _capturedHandoff = null;
  try {
    html.window.sessionStorage.remove(_sessionKey);
    html.window.sessionStorage.remove(_handoffKey);
  } catch (_) {}
}

String? _readTokenFromBrowser() {
  try {
    final fromSession = html.window.sessionStorage[_sessionKey];
    if (fromSession != null && fromSession.isNotEmpty) {
      return fromSession;
    }
  } catch (_) {}

  try {
    final frag = html.window.location.hash;
    if (frag.startsWith('#')) {
      final params = Uri.splitQueryString(frag.substring(1));
      final fromHash = params['am_token'] ?? params['access_token'];
      if (fromHash != null && fromHash.isNotEmpty) {
        return fromHash;
      }
    }
  } catch (_) {}

  final qp = Uri.base.queryParameters;
  final fromQuery = qp['am_token'] ?? qp['token'];
  if (fromQuery != null &&
      fromQuery.isNotEmpty &&
      !fromQuery.startsWith('mock_')) {
    return fromQuery;
  }
  return null;
}

String? _readHandoffFromBrowser() {
  try {
    final fromSession = html.window.sessionStorage[_handoffKey];
    if (fromSession != null && fromSession.isNotEmpty) {
      return fromSession;
    }
  } catch (_) {}

  try {
    final frag = html.window.location.hash;
    if (frag.startsWith('#')) {
      final params = Uri.splitQueryString(frag.substring(1));
      final fromHash = params['handoff'];
      if (fromHash != null && fromHash.isNotEmpty) {
        return fromHash;
      }
    }
  } catch (_) {}

  final fromQuery = Uri.base.queryParameters['handoff'];
  if (fromQuery != null && fromQuery.isNotEmpty) {
    return fromQuery;
  }
  return null;
}

void _stripHandoffFromUrl() {
  try {
    final uri = Uri.base;
    final qp = Map<String, String>.from(uri.queryParameters)
      ..remove('am_token')
      ..remove('token')
      ..remove('handoff');
    final cleaned =
        uri.replace(queryParameters: qp.isEmpty ? null : qp, fragment: '');
    html.window.history.replaceState(null, '', cleaned.toString());
  } catch (_) {}
}
