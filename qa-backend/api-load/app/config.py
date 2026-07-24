from __future__ import annotations

import os

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

from app import env_urls


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "am-spt-poc"
    app_port: int = 8150
    app_env: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_ENV", "app_env"),
    )
    log_level: str = "INFO"
    root_path: str = ""

    # Empty → filled from APP_ENV / DEFAULT_ENVIRONMENT (public HTTPS). Override only when needed.
    poc_target_url: str = ""
    # Mounted ConfigMaps / local dir of service spt.yaml registrations
    catalog_external_dir: str = "/catalog-external"
    data_dir: str = "/data"
    # Persistence: json | dual | db (default db after cutover; use dual then json to rollback)
    spt_store: str = "db"
    # Empty → SQLite at {data_dir}/spt.db; set postgresql+psycopg://… for cluster
    spt_database_url: str | None = None
    # ACL: when True, mutating APIs require a valid API key (except local UI if key seeded open)
    spt_acl_required: bool = False
    # Bootstrap keys (plaintext, hashed on startup). Format role:name:secret
    # e.g. developer:local-dev:spt_sk_dev_localchange_me
    spt_bootstrap_keys: str = ""
    spt_max_concurrent_runs: int = 3
    spt_run_retention_days: int = 30
    k6_bin: str = "/usr/local/bin/k6"
    default_environment: str = "dev"
    spt_user_id: str = "ssd2658"
    spt_public_base_url: str = ""
    spt_identity_url: str = ""
    spt_auth_username: str = "ssd2658@gmail.com"
    spt_auth_password: str | None = None

    # Safety caps (preprod)
    max_vus: int = 50
    max_duration_seconds: int = 600

    # Shared infra (reuse cluster services)
    grafana_public_url: str = "https://grafana.asrax.in"
    grafana_k6_dashboard_uid: str = "spt-load-testing"
    influxdb_url: str = "http://influxdb.infra.svc.cluster.local:8086"
    influxdb_org: str = "am-portfolio"
    influxdb_bucket: str = "load-testing-dev"
    influxdb_token: str | None = None
    minio_endpoint: str = "http://minio.infra.svc.cluster.local:9000"
    minio_bucket: str = "load-testing"
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_public_console_url: str = "https://minio-console.asrax.in"

    # Testkube (optional — falls back to local k6)
    testkube_enabled: bool = False
    testkube_api_url: str = "http://testkube-api-server.load-testing.svc.cluster.local:8088"
    testkube_namespace: str = "load-testing"

    smoke_vus: int = 5
    smoke_duration: str = "30s"

    trace_body_max_bytes: int = 8000
    # Cap full request/response samples stored per run (inspector list)
    trace_max_calls: int = 500
    default_run_profile: str = "load"

    # Schema-first payload agent — LLM is HTTP fallback only (off by default)
    spt_payload_llm_fallback: bool = False
    spt_fin_api_testing_url: str | None = None

    # MCP enrich (am-mcp-server SSE) during ensure-working — before Try; LLM still last
    spt_payload_mcp_enrich: bool = Field(
        default=True,
        validation_alias=AliasChoices("SPT_PAYLOAD_MCP_ENRICH", "spt_payload_mcp_enrich"),
    )
    spt_mcp_server_url: str = Field(
        default="",
        validation_alias=AliasChoices("SPT_MCP_SERVER_URL", "spt_mcp_server_url"),
    )
    spt_mcp_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices("SPT_MCP_TIMEOUT_SECONDS", "spt_mcp_timeout_seconds"),
    )
    spt_mcp_user_id: str = Field(
        default="",
        validation_alias=AliasChoices("SPT_MCP_USER_ID", "spt_mcp_user_id"),
    )

    # Playwright UI runs via am-ui-test-agent (empty → public /ui-test for cluster APP_ENV)
    ui_test_agent_url: str = Field(
        default="",
        validation_alias=AliasChoices("SPT_UI_TEST_AGENT_URL", "UI_TEST_AGENT_URL"),
    )
    ui_test_default_profile: str = Field(
        default="AUTH_FLOW_MAIN",
        validation_alias=AliasChoices(
            "SPT_UI_TEST_DEFAULT_PROFILE", "UI_TEST_DEFAULT_PROFILE"
        ),
    )
    ui_test_poll_interval_s: float = Field(
        default=2.0,
        validation_alias=AliasChoices(
            "SPT_UI_TEST_POLL_INTERVAL_S", "UI_TEST_POLL_INTERVAL_S"
        ),
    )

    @model_validator(mode="after")
    def fill_product_urls(self) -> Self:
        env_key = self.app_env or self.default_environment
        canonical = env_urls.normalize_env(env_key) or env_urls.normalize_env(
            self.default_environment
        )
        # Cluster / named envs: derive public product URLs when unset or still cluster DNS.
        if canonical:
            if env_urls.needs_product_fill(self.poc_target_url):
                self.poc_target_url = env_urls.product_url(canonical, "analysis")
            if env_urls.needs_product_fill(self.spt_identity_url):
                self.spt_identity_url = env_urls.product_url(canonical, "identity")
            if env_urls.needs_product_fill(self.spt_public_base_url):
                self.spt_public_base_url = env_urls.public_host(canonical)
            if env_urls.needs_product_fill(self.ui_test_agent_url):
                self.ui_test_agent_url = env_urls.product_url(canonical, "ui_test")
            if not (self.spt_mcp_server_url or "").strip():
                # Pod → ClusterIP; laptop with APP_ENV=dev → public /mcp ingress
                if os.environ.get("KUBERNETES_SERVICE_HOST"):
                    self.spt_mcp_server_url = env_urls.infra_mcp_server(canonical)
                else:
                    self.spt_mcp_server_url = env_urls.public_mcp_server(canonical)
        else:
            # Local laptop defaults when nothing set
            if not (self.poc_target_url or "").strip():
                self.poc_target_url = env_urls.product_url("dev", "analysis")
            if not (self.spt_identity_url or "").strip():
                self.spt_identity_url = env_urls.product_url("dev", "identity")
            if not (self.spt_public_base_url or "").strip():
                self.spt_public_base_url = "http://localhost:8150"
            if not (self.ui_test_agent_url or "").strip():
                self.ui_test_agent_url = "http://localhost:8130"
            if not (self.spt_mcp_server_url or "").strip():
                self.spt_mcp_server_url = env_urls.public_mcp_server("dev")
        if not (self.spt_mcp_user_id or "").strip():
            self.spt_mcp_user_id = (self.spt_user_id or "").strip()
        return self


settings = Settings()
