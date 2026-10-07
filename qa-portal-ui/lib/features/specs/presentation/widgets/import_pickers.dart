import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';

Future<void> pickAndImportPostman(
  BuildContext context,
  SpecsCubit cubit, {
  required bool envOnly,
}) async {
  Map<String, dynamic>? collection = cubit.pendingImportCollection;
  Map<String, dynamic>? environment;

  if (!envOnly || collection == null) {
    final col = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['json'],
      withData: true,
      dialogTitle: 'Postman collection JSON',
    );
    if (col == null || col.files.isEmpty) return;
    final bytes = col.files.first.bytes;
    if (bytes == null) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not read collection file')),
        );
      }
      return;
    }
    try {
      final decoded = jsonDecode(utf8.decode(bytes));
      if (decoded is! Map) throw FormatException('collection must be a JSON object');
      collection = Map<String, dynamic>.from(decoded);
      cubit.pendingImportCollection = collection;
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Invalid collection JSON: $e')),
        );
      }
      return;
    }
  }

  // Offer env file (optional for collection import; required for env-only).
  final envPick = await FilePicker.platform.pickFiles(
    type: FileType.custom,
    allowedExtensions: const ['json'],
    withData: true,
    dialogTitle: envOnly
        ? 'Postman environment JSON'
        : 'Postman environment JSON (optional — Cancel to skip)',
  );
  if (envPick != null && envPick.files.isNotEmpty) {
    final bytes = envPick.files.first.bytes;
    if (bytes != null) {
      try {
        final decoded = jsonDecode(utf8.decode(bytes));
        if (decoded is Map) {
          environment = Map<String, dynamic>.from(decoded);
        }
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Invalid env JSON: $e')),
          );
        }
        return;
      }
    }
  } else if (envOnly) {
    return;
  }

  await cubit.importPostmanCollection(
    collection: collection,
    environment: environment,
  );
}


