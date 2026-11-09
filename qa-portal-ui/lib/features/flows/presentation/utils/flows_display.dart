// Display + client-side filter helpers for Flows sidebar / Run dataset pickers.

const kProfileDefault = 'default';
const kProfileFull = 'full';
const kProfilePremium = 'premium';

const kProfileChipOrder = [kProfileDefault, kProfileFull, kProfilePremium];

String _tagList(Map<String, dynamic> flow) {
  final tags = flow['tags'];
  if (tags is! List) return '';
  return tags.map((t) => '$t'.toLowerCase()).join(' ');
}

/// Normalize payload-set / flow profile labels → default|full|premium.
String? normalizeProfileLabel(String? raw) {
  final s = (raw ?? '').trim().toLowerCase();
  if (s.isEmpty) return null;
  if (s.contains('premium')) return kProfilePremium;
  if (s.contains('full')) return kProfileFull;
  if (s.contains('prod') ||
      s.contains('default') ||
      s.contains('working') ||
      s == 'v1' ||
      s.contains('data-gen-prod')) {
    return kProfileDefault;
  }
  return null;
}

/// Profile for a flow: tag `profile:*`, else inferred from id/title.
String? flowProfile(Map<String, dynamic> flow) {
  final tags = flow['tags'];
  if (tags is List) {
    for (final t in tags) {
      final s = '$t'.toLowerCase();
      if (s.startsWith('profile:')) {
        final n = normalizeProfileLabel(s.substring('profile:'.length));
        if (n != null) return n;
      }
    }
  }
  final blob = '${flow['id']} ${flow['title']} ${flow['description']}'.toLowerCase();
  return normalizeProfileLabel(blob);
}

/// Submodules from `module:*` tags, `flow:*`, or id heuristics.
List<String> flowSubmodules(Map<String, dynamic> flow) {
  final out = <String>[];
  final seen = <String>{};
  void add(String raw) {
    final m = raw.trim().toLowerCase().replaceAll(RegExp(r'[^a-z0-9_]+'), '_');
    if (m.isEmpty || !seen.add(m)) return;
    out.add(m);
  }

  final tags = flow['tags'];
  if (tags is List) {
    for (final t in tags) {
      final s = '$t'.toLowerCase();
      if (s.startsWith('module:')) {
        add(s.substring('module:'.length));
      } else if (s.startsWith('flow:')) {
        // flow id is not a module; map known tokens below
      }
    }
  }
  if (out.isNotEmpty) return out;

  final blob =
      '${flow['id']} ${flow['title']} ${_tagList(flow)}'.toLowerCase();
  const pairs = <(String, String)>[
    ('watchlist', 'watchlist'),
    ('index', 'market_index'),
    ('ipo', 'ipo'),
    ('mutual_fund', 'mutual_fund'),
    ('mf_', 'mutual_fund'),
    ('fundamental', 'fundamentals'),
    ('instrument', 'instrument'),
    ('search', 'instrument'),
    ('securit', 'securities'),
    ('ltp', 'market_data'),
    ('quote', 'market_data'),
    ('ohlc', 'market_data'),
  ];
  for (final (needle, mod) in pairs) {
    if (blob.contains(needle)) add(mod);
  }
  return out;
}

bool matchesProfileFilter(Map<String, dynamic> flow, String profileFilter) {
  if (profileFilter.isEmpty) return true;
  final want = normalizeProfileLabel(profileFilter) ?? profileFilter;
  final got = flowProfile(flow);
  if (want == kProfileDefault) {
    // Default = explicit default/prod OR untagged authored general flows.
    return got == null || got == kProfileDefault;
  }
  return got == want;
}

bool matchesSubmoduleFilter(Map<String, dynamic> flow, String submoduleFilter) {
  if (submoduleFilter.isEmpty) return true;
  final want = submoduleFilter.trim().toLowerCase();
  return flowSubmodules(flow).any((m) => m == want || m.contains(want));
}

/// Human title for list rows (hides raw dg_/FLOW_ noise when possible).
String flowDisplayTitle(Map<String, dynamic> flow) {
  final id = '${flow['id'] ?? ''}';
  final title = '${flow['title'] ?? ''}'.trim();
  final profile = flowProfile(flow);
  final profileSuffix = profile == null ? '' : ' · $profile';

  if (title.isNotEmpty &&
      title != id &&
      !title.startsWith('dg_') &&
      !RegExp(r'^FLOW_[A-Z0-9_]+$').hasMatch(title)) {
    // Already human, e.g. "Watchlist → LTP · default"
    if (profile != null && !title.toLowerCase().contains(profile)) {
      return '$title$profileSuffix';
    }
    return title;
  }

  var raw = title.isNotEmpty ? title : id;
  // am-market-data · watchlist_to_ltp (prod)
  final m = RegExp(
    r'^(?:am[-_][\w-]+\s*[·•]\s*)?([\w-]+)\s*(?:\(([^)]+)\))?$',
  ).firstMatch(raw);
  if (m != null) {
    raw = m.group(1) ?? raw;
    final fromParen = normalizeProfileLabel(m.group(2));
    final human = _humanizeToken(raw);
    final p = fromParen ?? profile;
    return p == null ? human : '$human · $p';
  }

  if (id.startsWith('dg_')) {
    // dg_am-market-data_prod_watchlist_to_ltp
    final parts = id.split('_');
    final flowParts = <String>[];
    var afterProfile = false;
    for (final p in parts.skip(1)) {
      if (!afterProfile &&
          {'prod', 'full', 'premium', 'default', 'working'}.contains(p)) {
        afterProfile = true;
        continue;
      }
      if (afterProfile) flowParts.add(p);
    }
    if (flowParts.isEmpty) {
      // fall through
    } else {
      final human = _humanizeToken(flowParts.join('_'));
      return profile == null ? human : '$human · $profile';
    }
  }

  if (id.startsWith('FLOW_')) {
    var rest = id.replaceFirst(RegExp(r'^FLOW_'), '');
    rest = rest.replaceFirst(RegExp(r'^(MARKET|PORTFOLIO|OMS|IDENTITY)_'), '');
    final human = _humanizeToken(rest.toLowerCase());
    return profile == null ? human : '$human · $profile';
  }

  return title.isNotEmpty ? title : id;
}

String flowDisplaySubtitle(Map<String, dynamic> flow) {
  final cat = '${flow['category'] ?? ''}'.trim();
  final source = '${flow['source'] ?? ''}'.trim();
  final nodes = flow['node_count'] ?? 0;
  final mods = flowSubmodules(flow);
  final profile = flowProfile(flow);
  return [
    if (profile != null) profile,
    if (mods.isNotEmpty) mods.take(2).join('+'),
    if (cat.isNotEmpty) cat,
    if (source.isNotEmpty) source,
    '$nodes step${nodes == 1 ? '' : 's'}',
  ].join(' · ');
}

String flowBadgeLabel(Map<String, dynamic> flow) {
  final profile = flowProfile(flow);
  if (profile != null) return profile.toUpperCase();
  final cat = '${flow['category'] ?? ''}'.trim();
  if (cat.isNotEmpty) return cat.toUpperCase();
  return 'FLOW';
}

String _humanizeToken(String raw) {
  final parts =
      raw.replaceAll('-', '_').split('_').where((p) => p.isNotEmpty).toList();
  if (parts.isEmpty) return raw;
  final ti = parts.indexOf('to');
  if (ti >= 0) {
    String words(List<String> xs) =>
        xs.map((x) => x.isEmpty ? x : '${x[0].toUpperCase()}${x.substring(1)}')
            .join(' ');
    final left = words(parts.sublist(0, ti));
    final right = words(parts.sublist(ti + 1));
    if (left.isNotEmpty && right.isNotEmpty) return '$left → $right';
  }
  return parts
      .map((x) => x.isEmpty ? x : '${x[0].toUpperCase()}${x.substring(1)}')
      .join(' ');
}

/// Map payload-set label → profile chip id.
String? profileFromPayloadSet(Map<String, dynamic> set) {
  return normalizeProfileLabel('${set['label'] ?? ''}');
}

/// Pick best matching payload-set version for a profile chip.
int? versionForProfile(List<Map<String, dynamic>> sets, String profile) {
  final want = normalizeProfileLabel(profile) ?? profile;
  for (final s in sets) {
    if (profileFromPayloadSet(s) == want) {
      return int.tryParse('${s['version']}');
    }
  }
  return null;
}

String payloadSetMenuLabel(Map<String, dynamic> set, {Object? active}) {
  final ver = set['version'];
  final label = '${set['label'] ?? ''}';
  final profile = normalizeProfileLabel(label);
  final pretty = profile ?? (label.isEmpty ? 'set' : label);
  final activeMark =
      active != null && '$ver' == '$active' ? ' (active)' : '';
  return 'v$ver · $pretty$activeMark';
}
