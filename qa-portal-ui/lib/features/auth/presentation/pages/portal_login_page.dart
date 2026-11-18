import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/auth/auth_service.dart';
import '../../../../core/auth/handoff_token.dart';
import '../../../../core/router/app_router.dart';

/// Dedicated QA Portal Login Page that delegates authentication to AM Central.
class PortalLoginPage extends StatefulWidget {
  const PortalLoginPage({super.key});

  @override
  State<PortalLoginPage> createState() => _PortalLoginPageState();
}

class _PortalLoginPageState extends State<PortalLoginPage> {
  bool _isLoading = false;
  String? _handoffError;

  @override
  void initState() {
    super.initState();
    _checkExistingSession();
  }

  void _checkExistingSession() {
    final auth = GetIt.instance<QaAuthService>();
    if (auth.isAuthenticated) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          context.go(AppRoutes.uiFlows);
        }
      });
    } else if (Uri.base.queryParameters['qa_sso'] == '1' ||
        readCentralHandoffCode() != null ||
        readCentralHandoffToken() != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(_handleCentralHandoff());
      });
    }
  }

  void _handleSignIn() {
    setState(() {
      _isLoading = true;
      _handoffError = null;
    });
    final auth = GetIt.instance<QaAuthService>();
    auth.redirectToCentralLogin();
  }

  Future<void> _handleCentralHandoff() async {
    setState(() {
      _isLoading = true;
      _handoffError = null;
    });
    final auth = GetIt.instance<QaAuthService>();
    try {
      final next = await auth.acceptCentralHandoff(state: AppRoutes.uiFlows);
      if (!mounted) return;
      context.go(next.startsWith('/') ? next : AppRoutes.uiFlows);
    } catch (e) {
      if (!mounted) return;
      String message =
          'AM Apps signed you in, but the QA session handoff failed. Sign in again.';
      if (e is DioException) {
        final detail = e.response?.data;
        if (detail is Map && detail['detail'] != null) {
          message = detail['detail'].toString();
        }
      } else {
        final raw = e.toString();
        if (raw.contains('Missing AM session')) {
          message =
              'AM Apps did not pass a session to the QA portal. Restart AM Apps with QA_API_BASE and try again.';
        } else if (raw.isNotEmpty) {
          message = raw.replaceFirst('Exception: ', '');
        }
      }
      setState(() {
        _isLoading = false;
        _handoffError = message;
      });
    }
  }

  Future<void> _handleKeycloakSignIn() async {
    setState(() => _isLoading = true);
    final auth = GetIt.instance<QaAuthService>();
    await auth.redirectToKeycloak(state: AppRoutes.uiFlows);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: const Color(0xFF090D16),
      body: Stack(
        children: [
          // Ambient background glow
          Positioned(
            top: -100,
            right: -100,
            child: Container(
              width: 500,
              height: 500,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFF38BDF8).withValues(alpha: 0.08),
              ),
            ),
          ),
          Positioned(
            bottom: -150,
            left: -100,
            child: Container(
              width: 600,
              height: 600,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFF6366F1).withValues(alpha: 0.06),
              ),
            ),
          ),
          Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Container(
                constraints: const BoxConstraints(maxWidth: 460),
                padding: const EdgeInsets.all(40),
                decoration: BoxDecoration(
                  color: const Color(0xFF131C2E).withValues(alpha: 0.95),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: const Color(0xFF26354D)),
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
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Brand Pill
                    Center(
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 6),
                        decoration: BoxDecoration(
                          color:
                              const Color(0xFF38BDF8).withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                              color: const Color(0xFF38BDF8)
                                  .withValues(alpha: 0.3)),
                        ),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.shield_outlined,
                                size: 14, color: Color(0xFF38BDF8)),
                            SizedBox(width: 6),
                            Text(
                              'AM CENTRAL IDENTITY',
                              style: TextStyle(
                                color: Color(0xFF38BDF8),
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 1.1,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),

                    // Title
                    Text(
                      'AM QA Portal',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.headlineMedium?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.5,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Autonomous Quality Engineering, UI Flows & Ecosystem Reliability Engine',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: const Color(0xFF94A3B8),
                        height: 1.5,
                      ),
                    ),
                    const SizedBox(height: 32),

                    // Feature highlights
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: const Color(0xFF0F172A),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFF1E293B)),
                      ),
                      child: Column(
                        children: [
                          _buildFeatureRow(Icons.auto_awesome,
                              'End-to-end automated UI flow execution'),
                          const SizedBox(height: 10),
                          _buildFeatureRow(Icons.api,
                              'Live OpenAPI validation & regression runs'),
                          const SizedBox(height: 10),
                          _buildFeatureRow(Icons.lock_outline,
                              'Secure role-gated operator permissions'),
                        ],
                      ),
                    ),
                    const SizedBox(height: 32),

                    if (_handoffError != null) ...[
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color:
                              const Color(0xFFEF4444).withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color:
                                const Color(0xFFEF4444).withValues(alpha: 0.35),
                          ),
                        ),
                        child: Text(
                          _handoffError!,
                          style: const TextStyle(
                            color: Color(0xFFFCA5A5),
                            fontSize: 12.5,
                            height: 1.4,
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                    ],

                    // Primary: AM Central. Keycloak is a fallback only.
                    ElevatedButton(
                      onPressed: _isLoading ? null : _handleSignIn,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF38BDF8),
                        foregroundColor: const Color(0xFF0F172A),
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: _isLoading
                          ? const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(
                                strokeWidth: 2.5,
                                valueColor: AlwaysStoppedAnimation<Color>(
                                    Color(0xFF0F172A)),
                              ),
                            )
                          : const Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.login_rounded, size: 20),
                                SizedBox(width: 10),
                                Text(
                                  'Sign In with AM Central',
                                  style: TextStyle(
                                    fontSize: 15,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ],
                            ),
                    ),
                    const SizedBox(height: 12),
                    TextButton(
                      onPressed: _isLoading
                          ? null
                          : () => unawaited(_handleKeycloakSignIn()),
                      child: const Text(
                        'Use Keycloak directly',
                        style: TextStyle(
                          color: Color(0xFF64748B),
                          fontSize: 12.5,
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),

                    const Text(
                      'Sign in on AM Apps. After authentication you return here with your operator session — no second Keycloak step.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Color(0xFF64748B),
                        fontSize: 11.5,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeatureRow(IconData icon, String text) {
    return Row(
      children: [
        Icon(icon, size: 16, color: const Color(0xFF38BDF8)),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            text,
            style: const TextStyle(
              color: Color(0xFFCBD5E1),
              fontSize: 12.5,
            ),
          ),
        ),
      ],
    );
  }
}
