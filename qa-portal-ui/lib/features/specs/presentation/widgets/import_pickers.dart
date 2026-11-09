import 'dart:convert';
import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../cubit/specs_cubit.dart';

/// Decode .json / .zip / .gz bytes into a JSON map (first .json member for zip).
Map<String, dynamic> decodePayloadBlob(Uint8List bytes, String filename) {
  final name = filename.toLowerCase();
  if (name.endsWith('.zip') ||
      (bytes.length >= 2 && bytes[0] == 0x50 && bytes[1] == 0x4b)) {
    final archive = ZipDecoder().decodeBytes(bytes);
    final files = archive.files
        .where((f) => f.isFile && !f.name.startsWith('__MACOSX'))
        .toList();
    if (files.isEmpty) {
      throw FormatException('zip has no files');
    }
    ArchiveFile pick = files.first;
    for (final f in files) {
      final n = f.name.toLowerCase();
      if (n.endsWith('.json') ||
          n.endsWith('payload.json') ||
          n.endsWith('import_body.json')) {
        pick = f;
        break;
      }
    }
    final decoded = jsonDecode(utf8.decode(pick.content as List<int>));
    if (decoded is! Map) {
      throw FormatException('zip JSON root must be an object');
    }
    return Map<String, dynamic>.from(decoded);
  }
  if (name.endsWith('.gz') ||
      name.endsWith('.gzip') ||
      (bytes.length >= 2 && bytes[0] == 0x1f && bytes[1] == 0x8b)) {
    final raw = GZipDecoder().decodeBytes(bytes);
    final decoded = jsonDecode(utf8.decode(raw));
    if (decoded is! Map) {
      throw FormatException('gzip JSON root must be an object');
    }
    return Map<String, dynamic>.from(decoded);
  }
  final decoded = jsonDecode(utf8.decode(bytes));
  if (decoded is! Map) {
    throw FormatException('JSON root must be an object');
  }
  return Map<String, dynamic>.from(decoded);
}

/// Zip a JSON object for upload (smaller than raw JSON over the wire).
Uint8List zipJsonObject(Map<String, dynamic> doc, {String member = 'payload.json'}) {
  final jsonBytes = utf8.encode(jsonEncode(doc));
  final archive = Archive()
    ..addFile(ArchiveFile(member, jsonBytes.length, jsonBytes));
  return Uint8List.fromList(ZipEncoder().encode(archive)!);
}

Future<void> pickAndImportPostman(
  BuildContext context,
  SpecsCubit cubit, {
  required bool envOnly,
}) async {
  Map<String, dynamic>? collection = cubit.pendingImportCollection;
  Map<String, dynamic>? environment;
  Uint8List? zipBytes;
  String? zipName;

  if (!envOnly || collection == null) {
    final col = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['json', 'zip', 'gz'],
      withData: true,
      dialogTitle: 'Payload / Postman collection (.json / .zip / .gz)',
    );
    if (col == null || col.files.isEmpty) return;
    final file = col.files.first;
    final bytes = file.bytes;
    if (bytes == null) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not read collection file')),
        );
      }
      return;
    }
    final name = file.name;
    final lower = name.toLowerCase();
    try {
      if (lower.endsWith('.zip') || lower.endsWith('.gz')) {
        // Prefer multipart zip upload (no inflate→rejson on client for huge packs).
        zipBytes = bytes;
        zipName = name;
        // Also decode so env merge / pending still works when zip wraps a collection.
        collection = decodePayloadBlob(bytes, name);
        cubit.pendingImportCollection = collection;
      } else {
        collection = decodePayloadBlob(bytes, name);
        cubit.pendingImportCollection = collection;
        // Large JSON → zip before send to cut latency.
        if (bytes.length > 32 * 1024) {
          zipBytes = zipJsonObject(collection);
          zipName = '${name.replaceAll(RegExp(r'\.json$', caseSensitive: false), '')}.zip';
        }
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Invalid collection file: $e')),
        );
      }
      return;
    }
  }

  // Offer env file (optional for collection import; required for env-only).
  final envPick = await FilePicker.platform.pickFiles(
    type: FileType.custom,
    allowedExtensions: const ['json', 'zip', 'gz'],
    withData: true,
    dialogTitle: envOnly
        ? 'Postman environment (.json / .zip)'
        : 'Postman environment (optional — Cancel to skip)',
  );
  if (envPick != null && envPick.files.isNotEmpty) {
    final bytes = envPick.files.first.bytes;
    if (bytes != null) {
      try {
        environment = decodePayloadBlob(bytes, envPick.files.first.name);
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Invalid env file: $e')),
          );
        }
        return;
      }
    }
  } else if (envOnly) {
    return;
  }

  if (zipBytes != null && zipName != null && environment == null) {
    await cubit.importPayloadZip(
      bytes: zipBytes,
      filename: zipName,
    );
    return;
  }

  await cubit.importPostmanCollection(
    collection: collection,
    environment: environment,
  );
}
