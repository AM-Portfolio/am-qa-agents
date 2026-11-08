import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/di/injection.dart';
import '../../../../core/router/app_router.dart';
import '../../../specs/data/specs_repository.dart';
import '../../../specs/presentation/widgets/import_pickers.dart';
import '../cubit/portal_notifications.dart';
import '../cubit/workspace_cubit.dart';

/// Header Import: load Postman collection (.json/.zip/.gz) into active workspace.
Future<void> showPortalImportDialog(BuildContext context) async {
  final wsCubit = context.read<WorkspaceCubit>();
  var active = wsCubit.state.active;
  if (active == null) {
    await wsCubit.load();
    active = wsCubit.state.active;
  }

  final serviceCtrl = TextEditingController(text: active?.defaultService ?? '');
  final envCtrl = TextEditingController(text: active?.environment ?? 'dev');
  String? pickedName;
  Uint8List? pickedBytes;
  Map<String, dynamic>? collection;
  var importing = false;
  String? status;

  await showDialog<void>(
    context: context,
    builder: (ctx) {
      return StatefulBuilder(
        builder: (ctx, setLocal) {
          Future<void> pickFile() async {
            final col = await FilePicker.platform.pickFiles(
              type: FileType.custom,
              allowedExtensions: const ['json', 'zip', 'gz'],
              withData: true,
              dialogTitle: 'Postman collection (.json / .zip / .gz)',
            );
            if (col == null || col.files.isEmpty) return;
            final file = col.files.first;
            final bytes = file.bytes;
            if (bytes == null) {
              setLocal(() => status = 'Could not read file');
              return;
            }
            try {
              final decoded = decodePayloadBlob(bytes, file.name);
              setLocal(() {
                pickedName = file.name;
                pickedBytes = bytes;
                collection = decoded;
                status = 'Loaded ${file.name}';
              });
            } catch (e) {
              setLocal(() => status = 'Invalid collection: $e');
            }
          }

          Future<void> runImport() async {
            final service = serviceCtrl.text.trim();
            if (service.isEmpty) {
              setLocal(() => status = 'Enter a service id (e.g. am-analysis)');
              return;
            }
            if (collection == null && pickedBytes == null) {
              setLocal(() => status = 'Pick a Postman collection file first');
              return;
            }
            setLocal(() {
              importing = true;
              status = 'Importing…';
            });
            try {
              final repo = getIt<SpecsRepository>();
              final name = (pickedName ?? 'collection.json').toLowerCase();
              Map<String, dynamic> out;
              if (pickedBytes != null &&
                  (name.endsWith('.zip') || name.endsWith('.gz'))) {
                out = await repo.importPayloadZip(
                  service: service,
                  bytes: pickedBytes!,
                  filename: pickedName!,
                );
              } else if (pickedBytes != null &&
                  collection != null &&
                  pickedBytes!.length > 32 * 1024) {
                final zip = zipJsonObject(collection!);
                out = await repo.importPayloadZip(
                  service: service,
                  bytes: zip,
                  filename: '${service}_import.zip',
                );
              } else {
                out = await repo.importCollection(
                  service: service,
                  collection: collection!,
                  format: 'postman',
                );
              }

              final env = envCtrl.text.trim().isEmpty ? 'dev' : envCtrl.text.trim();
              await wsCubit.saveActive(
                environment: env,
                defaultService: service,
              );
              if (ctx.mounted) {
                context.read<PortalNotificationsCubit>().push(
                      'Imported ${out['imported'] ?? 0} → '
                      'v${out['payload_set_version'] ?? '?'} for $service',
                      isError: false,
                    );
                Navigator.pop(ctx);
                context.go(
                  '${AppRoutes.specs}?spec=${Uri.encodeComponent(service)}',
                );
              }
            } catch (e) {
              setLocal(() {
                importing = false;
                status = 'Import failed: $e';
              });
              if (ctx.mounted) {
                context.read<PortalNotificationsCubit>().push(
                      'Import failed: $e',
                    );
              }
            }
          }

          return AlertDialog(
            title: const Row(
              children: [
                Icon(Icons.upload_file_outlined),
                SizedBox(width: 8),
                Text('Import Postman'),
              ],
            ),
            content: SizedBox(
              width: 420,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Load a Postman collection export into the active workspace '
                    '(service payload set).',
                    style: Theme.of(ctx).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: serviceCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Service',
                      hintText: 'am-analysis',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: envCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Environment',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: importing ? null : pickFile,
                    icon: const Icon(Icons.folder_open),
                    label: Text(
                      pickedName == null
                          ? 'Choose collection file'
                          : 'File: $pickedName',
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: importing
                        ? null
                        : () {
                            Navigator.pop(ctx);
                            final svc = serviceCtrl.text.trim();
                            if (svc.isEmpty) {
                              context.go(AppRoutes.specs);
                            } else {
                              context.go(
                                '${AppRoutes.specs}?spec=${Uri.encodeComponent(svc)}',
                              );
                            }
                          },
                    child: const Text('Open OpenAPI Data tab instead'),
                  ),
                  if (status != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      status!,
                      style: TextStyle(
                        color: status!.startsWith('Import failed') ||
                                status!.startsWith('Invalid') ||
                                status!.startsWith('Could') ||
                                status!.startsWith('Enter') ||
                                status!.startsWith('Pick')
                            ? Theme.of(ctx).colorScheme.error
                            : Theme.of(ctx).colorScheme.primary,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: importing ? null : () => Navigator.pop(ctx),
                child: const Text('Cancel'),
              ),
              FilledButton.icon(
                onPressed: importing ? null : runImport,
                icon: importing
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.upload),
                label: Text(importing ? 'Importing…' : 'Import'),
              ),
            ],
          );
        },
      );
    },
  );
}
