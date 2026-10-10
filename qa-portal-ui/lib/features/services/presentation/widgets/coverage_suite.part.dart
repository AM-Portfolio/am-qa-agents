part of 'coverage_board.dart';

class _SuiteView {
  const _SuiteView({
    required this.id,
    required this.level,
    required this.name,
    required this.category,
    required this.plain,
    required this.envAction,
    required this.cases,
  });

  final String id;
  final String level;
  final String name;
  final String category;
  final String plain;
  final String envAction;
  final List<Map<String, dynamic>> cases;
}

class _SuitePanel extends StatelessWidget {
  const _SuitePanel({
    required this.suite,
    required this.accent,
    required this.expanded,
    required this.onToggle,
    required this.onRun,
    required this.onAllRuns,
    required this.onOpenApi,
    required this.plainTitle,
    required this.plainStep,
    required this.surface,
    required this.outline,
  });

  final _SuiteView suite;
  final Color accent;
  final bool expanded;
  final VoidCallback onToggle;
  final VoidCallback onRun;
  final VoidCallback onAllRuns;
  final VoidCallback onOpenApi;
  final String Function(String) plainTitle;
  final String Function(String) plainStep;
  final Color surface;
  final Color outline;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: surface.withValues(alpha: 0.35),
      borderRadius: BorderRadius.circular(14),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onToggle,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: outline.withValues(alpha: 0.4)),
          ),
          clipBehavior: Clip.antiAlias,
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(width: 5, color: accent),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
                    child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: accent.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      suite.level,
                      style: TextStyle(
                        color: accent,
                        fontWeight: FontWeight.w800,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      suite.name,
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                      ),
                    ),
                  ),
                  Icon(
                    expanded
                        ? Icons.expand_less_rounded
                        : Icons.expand_more_rounded,
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                suite.plain.isEmpty
                    ? 'Suite of automated checks for this service.'
                    : suite.plain,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppColors.textSecondaryDark,
                      height: 1.35,
                    ),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  _Tag(suite.category, accent),
                  _Tag('${suite.cases.length} test cases', accent),
                  _Tag('Policy: ${suite.envAction}', accent),
                  TextButton.icon(
                    onPressed: onAllRuns,
                    icon: const Icon(Icons.history, size: 16),
                    label: const Text('Runs'),
                  ),
                  FilledButton.tonalIcon(
                    onPressed: onRun,
                    icon: const Icon(Icons.play_arrow_rounded, size: 18),
                    label: const Text('Run suite'),
                  ),
                ],
              ),
              if (expanded) ...[
                const SizedBox(height: 14),
                Divider(color: outline.withValues(alpha: 0.5)),
                const SizedBox(height: 10),
                Text(
                  'Test cases',
                  style: Theme.of(context)
                      .textTheme
                      .titleSmall
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                if (suite.cases.isEmpty)
                  Text(
                    'No invented cases in this suite yet.',
                    style: Theme.of(context).textTheme.bodySmall,
                  )
                else
                  GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: suite.cases.length,
                    gridDelegate:
                        const SliverGridDelegateWithMaxCrossAxisExtent(
                      maxCrossAxisExtent: 340,
                      mainAxisExtent: 188,
                      crossAxisSpacing: 10,
                      mainAxisSpacing: 10,
                    ),
                    itemBuilder: (context, i) => _CaseCard(
                      index: i + 1,
                      data: suite.cases[i],
                      accent: accent,
                      plainTitle: plainTitle,
                      plainStep: plainStep,
                      onOpenApi: onOpenApi,
                      onRun: onRun,
                    ),
                  ),
              ],
            ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

