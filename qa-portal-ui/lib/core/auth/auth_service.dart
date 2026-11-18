import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import '../config/portal_config.dart';
import 'handoff_token.dart';

class QaUser {
  final String username;
  final String? email;
  final List<String> roles;

  const QaUser({
    required this.username,
    this.email,
    this.roles = const [],
  });

  bool get isQaOperator =>
      roles.contains('access-qa-portal') ||
      roles.contains('qa_operator') ||
      roles.contains('qa_admin') ||
      roles.contains('admin') ||
      roles.contains('am-admin');

  factory QaUser.fromJson(Map<String, dynamic> json) {
    return QaUser(
      username: (json['username'] as String?) ?? 'QA Operator',
      email: json['email'] as String?,
      roles: (json['roles'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() => {
        'username': username,
        'email': email,
        'roles': roles,
      };
}

class QaAuthService {
  static const _tokenKey = 'am_qa_access_token';
  static const _userKey = 'am_qa_user_info';
  static const _pkceVerifierKey = 'am_qa_oidc_pkce_verifier';
  static const _oidcStateKey = 'am_qa_oidc_state';
  static const _returnPathKey = 'am_qa_oidc_return_path';
  static const _issuer = String.fromEnvironment(
    'KEYCLOAK_ISSUER',
    defaultValue: 'https://auth.asrax.in/realms/am-qa-agents-dev',
  );
  static const _clientId = String.fromEnvironment(
    'KEYCLOAK_CLIENT_ID',
    defaultValue: 'am-qa-portal-client',
  );

  /// Modern UI login URL. Empty = same-origin `/login` (am-dev ingress).
  static const _centralLoginUrl = String.fromEnvironment(
    'CENTRAL_LOGIN_URL',
    defaultValue: '',
  );

  final PortalConfig config;
  final Dio dio;

  String? _accessToken;
  QaUser? _currentUser;

  QaAuthService({
    required this.config,
    required this.dio,
  });

  bool get isAuthenticated => _accessToken != null && _accessToken!.isNotEmpty;
  QaUser? get currentUser => _currentUser;
  String? get accessToken => _accessToken;

  Future<void> init() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _accessToken = prefs.getString(_tokenKey);
      if (_accessToken != null && _accessToken!.isNotEmpty) {
        dio.options.headers['Authorization'] = 'Bearer $_accessToken';
      }
      final rawUser = prefs.getString(_userKey);
      if (rawUser != null && rawUser.isNotEmpty) {
        try {
          final map = jsonDecode(rawUser) as Map<String, dynamic>;
          _currentUser = QaUser.fromJson(map);
        } catch (_) {}
      }
    } catch (_) {}
  }

  Future<void> redirectToKeycloak({String? state}) async {
    final defaultCallback = _callbackUri;
    final verifier = _randomToken();
    final oidcState = _randomToken();
    final challenge = base64Url
        .encode(sha256.convert(utf8.encode(verifier)).bytes)
        .replaceAll('=', '');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_pkceVerifierKey, verifier);
    await prefs.setString(_oidcStateKey, oidcState);
    await prefs.setString(_returnPathKey, state ?? Uri.base.path);

    final keycloakAuthUri =
        Uri.parse('$_issuer/protocol/openid-connect/auth').replace(
      queryParameters: {
        'client_id': _clientId,
        'redirect_uri': defaultCallback,
        'response_type': 'code',
        'scope': 'openid profile email',
        'kc_idp_hint': 'am-dev',
        'state': oidcState,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
      },
    );

    await launchUrl(keycloakAuthUri, webOnlyWindowName: '_self');
  }

  String _randomToken() {
    final bytes = List<int>.generate(32, (_) => Random.secure().nextInt(256));
    return base64Url.encode(bytes).replaceAll('=', '');
  }

  void redirectToCentralLogin() {
    // Modern UI authenticates the operator, then returns to /qa/ui/?qa_sso=1
    // with the AM access token stashed for central-session (no second Keycloak).
    final query = <String, String>{
      'redirect': '/qa/ui/',
      'qa_sso': '1',
    };
    final Uri loginUri;
    if (_centralLoginUrl.isNotEmpty) {
      final base = Uri.parse(_centralLoginUrl);
      loginUri = base.replace(
        path: (base.path.isEmpty || base.path == '/') ? '/login' : base.path,
        queryParameters: {...base.queryParameters, ...query},
      );
    } else {
      loginUri = Uri(
        scheme: Uri.base.scheme,
        host: Uri.base.host,
        port: Uri.base.hasPort ? Uri.base.port : null,
        path: '/login',
        queryParameters: query,
      );
    }
    launchUrl(loginUri, webOnlyWindowName: '_self');
  }

  /// Complete SSO after Modern UI handoff using a one-time code or AM token.
  Future<String> acceptCentralHandoff({String? state}) async {
    final handoff = readCentralHandoffCode();
    final token = readCentralHandoffToken();
    if ((handoff == null || handoff.isEmpty) &&
        (token == null || token.isEmpty)) {
      throw StateError(
        'Missing AM session after Central Login. Sign in again from the QA portal.',
      );
    }
    try {
      return await acceptCentralToken(
        token ?? '',
        state: state,
        handoff: handoff,
      );
    } finally {
      clearCentralHandoffToken();
    }
  }

  Future<String> acceptCentralToken(
    String token, {
    String? state,
    String? handoff,
  }) async {
    // Paths are relative to Dio baseUrl (apiBase). Do NOT prefix apiBase again —
    // Dio concatenates baseUrl + path, so `/qa` + `/qa/api/...` becomes `/qa/qa/...`.
    final response = await dio.post<Map<String, dynamic>>(
      '/api/v1/auth/central-session',
      data: {
        if (handoff != null && handoff.isNotEmpty) 'handoff': handoff,
        if (token.isNotEmpty) 'access_token': token,
        'state': (state != null && state.startsWith('/')) ? state : '/ui-flows',
      },
    );

    final data = response.data ?? {};
    final accessToken = (data['access_token'] as String?) ?? '';
    final returnState = (data['state'] as String?) ?? '/ui-flows';
    if (accessToken.isEmpty) {
      throw StateError('Central session response missing access_token');
    }

    _accessToken = accessToken;
    dio.options.headers['Authorization'] = 'Bearer $accessToken';

    final userData = data['user'] as Map<String, dynamic>?;
    if (userData != null) {
      _currentUser = QaUser.fromJson(userData);
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, accessToken);
    if (_currentUser != null) {
      await prefs.setString(_userKey, jsonEncode(_currentUser!.toJson()));
    }
    await prefs.remove('qa_portal_signed_out');
    return returnState.startsWith('/') ? returnState : '/ui-flows';
  }

  String get _callbackUri {
    final rootPath = config.rootPath.replaceAll(RegExp(r'/$'), '');
    final callbackPath =
        rootPath.isEmpty ? '/callback' : '$rootPath/ui/callback';
    return Uri.base.origin + callbackPath;
  }

  Future<String> saveDirectSession({
    required String token,
    String? username,
    String? email,
    List<String> roles = const ['qa_operator', 'admin'],
    String? state,
  }) async {
    _accessToken = token;
    _currentUser = QaUser(
      username: username ?? email ?? 'QA Operator',
      email: email,
      roles: roles,
    );
    dio.options.headers['Authorization'] = 'Bearer $token';

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
    await prefs.setString(_userKey, jsonEncode(_currentUser!.toJson()));
    await prefs.remove('qa_portal_signed_out');

    return (state != null && state.startsWith('/')) ? state : '/ui-flows';
  }

  Future<String> exchangeCode({
    required String code,
    String? state,
    String? email,
    String? username,
    String? roles,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final expectedState = prefs.getString(_oidcStateKey);
    final verifier = prefs.getString(_pkceVerifierKey);
    if (state == null || state != expectedState || verifier == null) {
      throw StateError('Invalid or expired QA sign-in session. Please retry.');
    }
    final returnPath = prefs.getString(_returnPathKey) ?? '/ui-flows';
    final defaultRedirectUri = _callbackUri;

    final response = await dio.post<Map<String, dynamic>>(
      '/api/v1/auth/callback',
      data: {
        'code': code,
        'state': returnPath,
        'code_verifier': verifier,
        'redirect_uri': defaultRedirectUri,
        if (email != null && email.isNotEmpty) 'email': email,
        if (username != null && username.isNotEmpty) 'username': username,
        if (roles != null && roles.isNotEmpty) 'roles': roles,
      },
    );

    final data = response.data ?? {};
    final token = (data['access_token'] as String?) ?? '';
    final returnState = (data['state'] as String?) ?? '/runs';

    if (token.isNotEmpty) {
      _accessToken = token;
      dio.options.headers['Authorization'] = 'Bearer $token';

      final userData = data['user'] as Map<String, dynamic>?;
      if (userData != null) {
        _currentUser = QaUser.fromJson(userData);
      }

      await prefs.setString(_tokenKey, token);
      if (_currentUser != null) {
        await prefs.setString(_userKey, jsonEncode(_currentUser!.toJson()));
      }
      await prefs.remove(_pkceVerifierKey);
      await prefs.remove(_oidcStateKey);
      await prefs.remove(_returnPathKey);
    }

    return returnState;
  }

  Future<void> logout() async {
    _accessToken = null;
    _currentUser = null;
    dio.options.headers.remove('Authorization');
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    await prefs.remove(_userKey);
  }
}
