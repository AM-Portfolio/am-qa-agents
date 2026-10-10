import 'package:url_launcher/url_launcher.dart';

import '../../../../core/config/portal_config.dart';
import '../../../../core/di/injection.dart';
import '../../../../core/network/json_lists.dart';
import 'specs_cubit_host.mixin.dart';

mixin SpecsCubitDataIoMixin on SpecsCubitHost {
  Future<void> generateAllPayloads() async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    emit(
      state.copyWith(
        generating: true,
        clearGenerate: true,
        message: 'Generating payloads for ${state.apis.length} APIs…',
      ),
    );
    try {
      final out = await repo.generateAllPayloads(
        service: svc,
        environment: state.environment,
      );
      final rows = mapList(out, keys: const ['results', 'items']);
      await loadPayloadSets(svc, resetVersion: false);
      final verOut = out['payload_set_version'];
      emit(
        state.copyWith(
          generating: false,
          generateResults: rows,
          generateSummary: {
            'total': out['total'],
            'passed': out['passed'],
            'failed': out['failed'],
            'payload_set_version': verOut,
            'from_generate': true,
          },
          selectedPayloadVersion:
              verOut != null ? '$verOut' : state.selectedPayloadVersion,
          message:
              'Data prep done: ${out['passed'] ?? 0} passed / ${out['failed'] ?? 0} failed'
              ' (set v${verOut ?? '?'})',
        ),
      );
    } catch (e) {
      emit(
        state.copyWith(
          generating: false,
          message: 'Generate-all failed: $e',
        ),
      );
    }
  }

  /// Start Specs onboard prep workflow; polls until steps[] report is ready.
  Future<void> importPostmanCollection({
    required Map<String, dynamic> collection,
    Map<String, dynamic>? environment,
  }) async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    emit(state.copyWith(generating: true, message: 'Importing collection…'));
    try {
      final out = await repo.importCollection(
        service: svc,
        collection: collection,
        environment: environment,
        format: 'postman',
      );
      final ver = '${out['payload_set_version'] ?? ''}';
      await loadPayloadSets(svc, resetVersion: true);
      if (ver.isNotEmpty) {
        await setPayloadVersion(ver);
      }
      emit(
        state.copyWith(
          generating: false,
          message:
              'Imported ${out['imported'] ?? 0} requests → set v${out['payload_set_version'] ?? '?'}'
              '${(out['warnings'] is List && (out['warnings'] as List).isNotEmpty) ? ' (${(out['warnings'] as List).length} warnings)' : ''}',
        ),
      );
    } catch (e) {
      emit(state.copyWith(generating: false, message: 'Import failed: $e'));
    }
  }

  /// Import a .zip / .gz / large JSON pack via multipart (compressed on the wire).
  Future<void> importPayloadZip({
    required List<int> bytes,
    required String filename,
  }) async {
    final svc = state.selectedService;
    if (svc == null) {
      emit(state.copyWith(message: 'Select a service first'));
      return;
    }
    emit(
      state.copyWith(
        generating: true,
        message: 'Importing ${filename} (${bytes.length} bytes)…',
      ),
    );
    try {
      final out = await repo.importPayloadZip(
        service: svc,
        bytes: bytes,
        filename: filename,
      );
      final ver = '${out['payload_set_version'] ?? ''}';
      await loadPayloadSets(svc, resetVersion: true);
      if (ver.isNotEmpty) {
        await setPayloadVersion(ver);
      }
      final xfer = out['transfer'] is Map
          ? Map<String, dynamic>.from(out['transfer'] as Map)
          : null;
      emit(
        state.copyWith(
          generating: false,
          message:
              'Imported ${out['imported'] ?? 0} → set v${out['payload_set_version'] ?? '?'}'
              '${xfer != null ? ' · ${xfer['encoding']} ${xfer['bytes_in']}B' : ''}',
        ),
      );
    } catch (e) {
      emit(state.copyWith(generating: false, message: 'Zip import failed: $e'));
    }
  }

  Future<List<int>?> exportPayloadZip() async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    if (svc == null || ver == null) {
      emit(state.copyWith(message: 'Select a service and payload version'));
      return null;
    }
    try {
      final bytes = await repo.exportPayloadSetZip(service: svc, version: ver);
      emit(
        state.copyWith(
          message: 'Exported $svc v$ver zip (${bytes.length} bytes)',
        ),
      );
      return bytes;
    } catch (e) {
      emit(state.copyWith(message: 'Export zip failed: $e'));
      return null;
    }
  }

  /// Open compressed export in the browser (same-origin download).
  Future<void> downloadPayloadZip() async {
    final svc = state.selectedService;
    final ver = state.selectedPayloadVersion;
    if (svc == null || ver == null) {
      emit(state.copyWith(message: 'Select a service and payload version'));
      return;
    }
    try {
      final cfg = getIt.isRegistered<PortalConfig>()
          ? getIt<PortalConfig>()
          : null;
      final base = (cfg?.apiBase ?? '/qa').replaceAll(RegExp(r'/$'), '');
      final uri = Uri.parse('$base/api/payload-sets/$svc/$ver/export.zip');
      final ok = await launchUrl(uri, webOnlyWindowName: '_blank');
      emit(
        state.copyWith(
          message: ok
              ? 'Downloading $svc v$ver.zip'
              : 'Could not open export URL',
        ),
      );
    } catch (e) {
      emit(state.copyWith(message: 'Export zip failed: $e'));
    }
  }
}
