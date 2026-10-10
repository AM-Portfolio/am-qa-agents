// Fail if any lib/**/*.dart exceeds maxLines (default 600).
// Usage: dart run tool/check_max_lines.dart
import 'dart:io';

void main(List<String> args) {
  final maxLines = args.isNotEmpty ? int.tryParse(args.first) ?? 600 : 600;
  final lib = Directory('lib');
  if (!lib.existsSync()) {
    stderr.writeln('lib/ not found — run from qa-portal-ui root');
    exit(2);
  }
  final offenders = <({String path, int lines})>[];
  for (final entity in lib.listSync(recursive: true)) {
    if (entity is! File || !entity.path.endsWith('.dart')) continue;
    final lines = entity.readAsLinesSync().length;
    if (lines > maxLines) {
      offenders.add((path: entity.path.replaceAll('\\', '/'), lines: lines));
    }
  }
  offenders.sort((a, b) => b.lines.compareTo(a.lines));
  if (offenders.isEmpty) {
    stdout.writeln('OK — no lib/**/*.dart files over $maxLines lines');
    exit(0);
  }
  stdout.writeln('Files over $maxLines lines:');
  for (final o in offenders) {
    stdout.writeln('  ${o.lines}\t${o.path}');
  }
  stdout.writeln('${offenders.length} offender(s)');
  exit(1);
}
