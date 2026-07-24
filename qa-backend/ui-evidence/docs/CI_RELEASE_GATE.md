# CI note — wire in am-pipelines when ready
#
# Job sketch:
#   - checkout am-agents + am-modern-ui
#   - pip install ui-test-agent requirements + playwright chromium
#   - python scripts/check_routes_sync.py
#   - python scripts/run_suite.py --suite release_gate \
#       --target-file ../am-modern-ui/testing/targets.preprod.json \
#       --target release_gate
#   - upload artifacts: REPORT_DIR suite-*.json, *.html, traces/
#
# Trigger: changes under am-modern-ui/am_app or ui-test-agent/
