# Example GitHub App manifest fields (create via github.com/settings/apps)

name: qa-agent
homepage_url: https://github.com/am-portfolio
webhook_url: https://qa-agent.example/webhooks/github
webhook_secret: <from vault>
# Permissions:
#   Checks: Read & write
#   Contents: Read
#   Metadata: Read
#   Pull requests: Read
#   Commit statuses: Read & write
# Events: workflow_run, push, pull_request, check_run

# Runtime env (Vault / Helm secret):
# GITHUB_APP_ID=
# GITHUB_APP_INSTALLATION_ID=
# GITHUB_APP_PRIVATE_KEY=  (PEM)
# GITHUB_WEBHOOK_SECRET=
# GITHUB_TOKEN=            (PAT fallback for L1 compare)
