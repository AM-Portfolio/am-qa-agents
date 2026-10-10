from pathlib import Path

root = Path(__file__).resolve().parents[1] / "lib/features/specs/presentation/cubit"
p = root / "specs_cubit_data.mixin.dart"
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
header = "".join(lines[:15])
inner = lines[15:-1]


def chunk(a: int, b: int) -> str:
    return "".join(inner[a - 1 : b])


data_core = chunk(1, 181) + chunk(440, 535) + chunk(638, 820)
data_io = chunk(182, 231) + chunk(315, 439)
uc_extra = chunk(232, 314) + chunk(581, 637)
test_extra = chunk(536, 580)

io_header = """import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/config/portal_config.dart';
import '../../../../core/di/injection.dart';
import '../../../../core/network/json_lists.dart';
import 'specs_cubit_host.mixin.dart';
import 'specs_state.dart';

"""

(root / "specs_cubit_data.mixin.dart").write_text(
    header + data_core + "}\n", encoding="utf-8"
)
(root / "specs_cubit_data_io.mixin.dart").write_text(
    io_header + "mixin SpecsCubitDataIoMixin on SpecsCubitHost {\n" + data_io + "}\n",
    encoding="utf-8",
)

uc = (root / "specs_cubit_usecases.mixin.dart").read_text(encoding="utf-8")
uc = uc.rstrip()
if not uc.endswith("}"):
    raise SystemExit("usecases mixin malformed")
uc = uc[:-1] + uc_extra + "}\n"
(root / "specs_cubit_usecases.mixin.dart").write_text(uc, encoding="utf-8")

te = (root / "specs_cubit_test.mixin.dart").read_text(encoding="utf-8")
te = te.rstrip()
if not te.endswith("}"):
    raise SystemExit("test mixin malformed")
te = te[:-1] + test_extra + "}\n"
(root / "specs_cubit_test.mixin.dart").write_text(te, encoding="utf-8")

main_path = root / "specs_cubit.dart"
main = main_path.read_text(encoding="utf-8")
if "specs_cubit_data_io" not in main:
    main = main.replace(
        "import 'specs_cubit_data.mixin.dart';",
        "import 'specs_cubit_data.mixin.dart';\n"
        "import 'specs_cubit_data_io.mixin.dart';",
    )
    main = main.replace(
        "SpecsCubitDataMixin,",
        "SpecsCubitDataMixin,\n        SpecsCubitDataIoMixin,",
    )
    main_path.write_text(main, encoding="utf-8")

for f in sorted(root.glob("specs_cubit*.dart")):
    print(f.name, len(f.read_text(encoding="utf-8").splitlines()))
