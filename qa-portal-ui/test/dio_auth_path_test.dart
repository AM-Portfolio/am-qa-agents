import 'package:flutter_test/flutter_test.dart';

/// Dio joins URLs by string-concatenating baseUrl + path (not Uri.resolve).
/// Auth calls must use paths under the Dio baseUrl — never re-prefix apiBase.
///
/// On VM tests Dio rejects relative baseUrl (`/qa`); production web allows it.
/// Mirror the concat rule Dio uses in RequestOptions.uri.
String dioJoin(String baseUrl, String path) {
  if (path.startsWith(RegExp(r'https?:'))) return path;
  return baseUrl + path;
}

void main() {
  test('auth paths under /qa baseUrl do not double the prefix', () {
    expect(
      dioJoin('/qa', '/api/v1/auth/central-session'),
      '/qa/api/v1/auth/central-session',
    );
    expect(
      dioJoin('/qa', '/api/v1/auth/callback'),
      '/qa/api/v1/auth/callback',
    );
  });

  test('re-prefixing apiBase produces the broken /qa/qa path', () {
    expect(
      dioJoin('/qa', '/qa/api/v1/auth/central-session'),
      '/qa/qa/api/v1/auth/central-session',
    );
  });
}
