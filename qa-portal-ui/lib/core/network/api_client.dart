import 'package:dio/dio.dart';

/// Thin Dio wrapper for api-load REST.
class ApiClient {
  ApiClient(this._dio);

  final Dio _dio;

  Future<Response<dynamic>> get(
    String path, {
    Map<String, dynamic>? query,
    Options? options,
  }) {
    return _dio.get<dynamic>(path, queryParameters: query, options: options);
  }

  Future<Response<T>> getTyped<T>(
    String path, {
    Map<String, dynamic>? query,
    Options? options,
  }) {
    return _dio.get<T>(path, queryParameters: query, options: options);
  }

  Future<Response<dynamic>> post(
    String path, {
    Object? data,
    Map<String, dynamic>? query,
    Duration? receiveTimeout,
    Options? options,
  }) {
    Options? opts = options;
    if (receiveTimeout != null) {
      opts = (opts ?? Options()).copyWith(receiveTimeout: receiveTimeout);
    }
    return _dio.post<dynamic>(
      path,
      data: data,
      queryParameters: query,
      options: opts,
    );
  }

  Future<Response<dynamic>> put(String path, {Object? data}) {
    return _dio.put<dynamic>(path, data: data);
  }

  Future<Response<dynamic>> delete(
    String path, {
    Object? data,
    Map<String, dynamic>? query,
  }) {
    return _dio.delete<dynamic>(path, data: data, queryParameters: query);
  }

  Future<Response<dynamic>> request(
    String path, {
    required String method,
    Object? data,
    Map<String, dynamic>? headers,
  }) {
    return _dio.request<dynamic>(
      path,
      data: data,
      options: Options(method: method, headers: headers, validateStatus: (_) => true),
    );
  }
}
