import 'package:dio/dio.dart';

/// Thin Dio wrapper for api-load REST.
class ApiClient {
  ApiClient(this._dio);

  final Dio _dio;

  Future<Response<dynamic>> get(
    String path, {
    Map<String, dynamic>? query,
  }) {
    return _dio.get<dynamic>(path, queryParameters: query);
  }

  Future<Response<dynamic>> post(
    String path, {
    Object? data,
    Map<String, dynamic>? query,
  }) {
    return _dio.post<dynamic>(path, data: data, queryParameters: query);
  }

  Future<Response<dynamic>> put(String path, {Object? data}) {
    return _dio.put<dynamic>(path, data: data);
  }

  Future<Response<dynamic>> delete(String path) {
    return _dio.delete<dynamic>(path);
  }
}
