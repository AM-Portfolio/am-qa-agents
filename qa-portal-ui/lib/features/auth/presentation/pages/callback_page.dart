import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../core/auth/auth_service.dart';
import '../../../../core/router/app_router.dart';

class CallbackPage extends StatefulWidget {
  final String? code;
  final String? state;
  final String? email;

  const CallbackPage({
    super.key,
    this.code,
    this.state,
    this.email,
  });

  @override
  State<CallbackPage> createState() => _CallbackPageState();
}

class _CallbackPageState extends State<CallbackPage> {
  String _statusMessage = 'Connecting with AM Central Identity...';
  bool _hasError = false;
  bool _isAccessDenied = false;
  String _errorTitle = 'Authentication Error';
  String _errorMessage = 'Unable to complete sign-in.';
  String? _attemptedEmail;

  @override
  void initState() {
    super.initState();
    _handleAuthCallback();
  }

  Future<void> _handleAuthCallback() async {
    setState(() {
      _hasError = false;
      _isAccessDenied = false;
      _statusMessage = 'Connecting with AM Central Identity...';
    });

    final returnState = widget.state ?? Uri.base.queryParameters['state'];
    final code = widget.code ??
        Uri.base.queryParameters['code'] ??
        Uri.base.queryParameters['token'];
    final qEmail = widget.email ?? Uri.base.queryParameters['email'];

    if (code == null || code.isEmpty) {
      setState(() {
        _hasError = true;
        _errorTitle = 'Authorization Failed';
        _errorMessage = 'Missing authorization code from the identity provider.';
        _attemptedEmail = qEmail;
      });
      return;
    }

    try {
      final auth = GetIt.instance<QaAuthService>();
      final nextPath = await auth.exchangeCode(
        code: code,
        state: returnState,
        email: qEmail,
        username: Uri.base.queryParameters['username'],
        roles: Uri.base.queryParameters['roles'],
      );

      if (mounted) {
        context.go(nextPath.startsWith('/') ? nextPath : '/ui-flows');
      }
    } catch (e) {
      if (!mounted) return;

      String title = 'Authentication Error';
      String message = 'An unexpected error occurred while verifying your session.';
      bool accessDenied = false;

      if (e is DioException) {
        final statusCode = e.response?.statusCode;
        final resData = e.response?.data;

        String? detailMsg;
        if (resData is Map && resData['detail'] != null) {
          detailMsg = resData['detail'].toString();
        } else if (resData is String && resData.isNotEmpty) {
          detailMsg = resData;
        }

        if (statusCode == 403) {
          accessDenied = true;
          title = 'Access Denied';
          message = detailMsg ??
              'Your account is not authorized to access the AM QA Portal. '
              'The "access-qa-portal" role must be assigned in Keycloak.';
        } else if (statusCode == 401) {
          title = 'Session Expired';
          message = detailMsg ?? 'Your login session has expired or is invalid. Please sign in again.';
        } else if (statusCode != null && statusCode >= 500) {
          title = 'Service Unavailable';
          message = 'The identity provider or QA agent service is currently unreachable. Please try again shortly.';
        } else if (detailMsg != null && detailMsg.isNotEmpty) {
          message = detailMsg;
        }
      } else {
        message = e.toString();
      }

      setState(() {
        _hasError = true;
        _isAccessDenied = accessDenied;
        _errorTitle = title;
        _errorMessage = message;
        _attemptedEmail = qEmail;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: const Color(0xFF090D16),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Container(
            constraints: const BoxConstraints(maxWidth: 480),
            padding: const EdgeInsets.all(36),
            decoration: BoxDecoration(
              color: const Color(0xFF131C2E).withValues(alpha: 0.95),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: _isAccessDenied
                    ? const Color(0xFFEF4444).withValues(alpha: 0.3)
                    : const Color(0xFF26354D),
              ),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x60000000),
                  blurRadius: 32,
                  offset: Offset(0, 16),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (!_hasError) ...[
                  const SizedBox(
                    width: 52,
                    height: 52,
                    child: CircularProgressIndicator(
                      strokeWidth: 3,
                      valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF38BDF8)),
                    ),
                  ),
                  const SizedBox(height: 24),
                  Text(
                    'Authenticating QA Operator',
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 18,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _statusMessage,
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: const Color(0xFF94A3B8),
                    ),
                  ),
                ] else if (_isAccessDenied) ...[
                  // Access Denied Shield Icon
                  Container(
                    width: 68,
                    height: 68,
                    decoration: BoxDecoration(
                      color: const Color(0xFFEF4444).withValues(alpha: 0.12),
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: const Color(0xFFEF4444).withValues(alpha: 0.3),
                        width: 1.5,
                      ),
                    ),
                    child: const Icon(
                      Icons.lock_person_outlined,
                      color: Color(0xFFEF4444),
                      size: 34,
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Title
                  Text(
                    _errorTitle,
                    style: theme.textTheme.headlineSmall?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.3,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Unauthorized Operator Account',
                    style: TextStyle(
                      color: Color(0xFFF87171),
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),

                  // Attempted Account Badge
                  if (_attemptedEmail != null && _attemptedEmail!.isNotEmpty) ...[
                    const SizedBox(height: 18),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        color: const Color(0xFF0F172A),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: const Color(0xFF1E293B)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          CircleAvatar(
                            radius: 12,
                            backgroundColor: const Color(0xFFEF4444).withValues(alpha: 0.2),
                            child: Text(
                              _attemptedEmail![0].toUpperCase(),
                              style: const TextStyle(
                                color: Color(0xFFEF4444),
                                fontWeight: FontWeight.bold,
                                fontSize: 11,
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Flexible(
                            child: Text(
                              _attemptedEmail!,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: Color(0xFFE2E8F0),
                                fontWeight: FontWeight.w600,
                                fontSize: 13,
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: const Color(0xFFEF4444).withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'NO QA ROLE',
                              style: TextStyle(
                                color: Color(0xFFFCA5A5),
                                fontSize: 9.5,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 0.5,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],

                  const SizedBox(height: 18),

                  // Guidance / Detail Card
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0F172A),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFF1E293B)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.shield_outlined, size: 15, color: Color(0xFF38BDF8)),
                            SizedBox(width: 8),
                            Text(
                              'Why is this blocked?',
                              style: TextStyle(
                                color: Color(0xFF38BDF8),
                                fontWeight: FontWeight.w700,
                                fontSize: 12.5,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          _errorMessage,
                          style: const TextStyle(
                            color: Color(0xFF94A3B8),
                            fontSize: 12.5,
                            height: 1.45,
                          ),
                        ),
                        const SizedBox(height: 10),
                        const Divider(color: Color(0xFF1E293B), height: 1),
                        const SizedBox(height: 10),
                        const Text(
                          'To grant access, an administrator must assign the access-qa-portal role to this user in the Keycloak admin console (am-qa-agents-dev).',
                          style: TextStyle(
                            color: Color(0xFF64748B),
                            fontSize: 11.5,
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 26),

                  // Action Buttons
                  ElevatedButton.icon(
                    onPressed: () {
                      context.go(AppRoutes.login);
                    },
                    icon: const Icon(Icons.switch_account_outlined, size: 18),
                    label: const Text(
                      'Sign In with Another Account',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF38BDF8),
                      foregroundColor: const Color(0xFF0F172A),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      minimumSize: const Size.fromHeight(48),
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    onPressed: () {
                      launchUrl(
                        Uri.parse('http://localhost:9000/app/dashboard'),
                        webOnlyWindowName: '_self',
                      );
                    },
                    icon: const Icon(Icons.arrow_back_rounded, size: 16),
                    label: const Text('Return to AM Platform'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF94A3B8),
                      side: const BorderSide(color: Color(0xFF334155)),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      minimumSize: const Size.fromHeight(44),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: _handleAuthCallback,
                    child: const Text(
                      'Retry Sign In',
                      style: TextStyle(
                        color: Color(0xFF64748B),
                        fontSize: 12,
                      ),
                    ),
                  ),
                ] else ...[
                  // Generic Error
                  Container(
                    width: 60,
                    height: 60,
                    decoration: BoxDecoration(
                      color: const Color(0xFFEF4444).withValues(alpha: 0.12),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.error_outline_rounded,
                      color: Color(0xFFEF4444),
                      size: 32,
                    ),
                  ),
                  const SizedBox(height: 18),
                  Text(
                    _errorTitle,
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _errorMessage,
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: const Color(0xFF94A3B8),
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 24),
                  ElevatedButton.icon(
                    onPressed: () {
                      context.go(AppRoutes.login);
                    },
                    icon: const Icon(Icons.arrow_back_rounded, size: 16),
                    label: const Text('Back to Login'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF38BDF8),
                      foregroundColor: const Color(0xFF0F172A),
                      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
