from ui_evidence.api.portal_access import (
    QA_PORTAL_ACCESS_ROLES,
    authorize_portal_access,
    parse_email_allowlist,
)


def test_allowlist_grants_access():
    roles = authorize_portal_access(
        email="munish.prime@gmail.com",
        token_roles=[],
        required_roles=QA_PORTAL_ACCESS_ROLES,
        email_allowlist=parse_email_allowlist(
            "munish.prime@gmail.com,adhikarisoumya7@gmail.com,adhikariguddu07@gmail.com"
        ),
        session_roles_on_allowlist=["access-qa-portal", "qa_operator"],
    )
    assert "access-qa-portal" in roles
    assert "qa_operator" in roles


def test_unknown_email_denied():
    try:
        authorize_portal_access(
            email="random.user@example.com",
            token_roles=[],
            required_roles=QA_PORTAL_ACCESS_ROLES,
            email_allowlist=parse_email_allowlist("munish.prime@gmail.com"),
            session_roles_on_allowlist=["access-qa-portal"],
        )
        assert False, "expected deny"
    except ValueError as exc:
        assert "Access denied" in str(exc)


def test_keycloak_role_grants_without_allowlist():
    roles = authorize_portal_access(
        email="anyone@asrax.in",
        token_roles=["access-qa-portal", "offline_access"],
        required_roles=QA_PORTAL_ACCESS_ROLES,
        email_allowlist=set(),
        session_roles_on_allowlist=["access-qa-portal"],
    )
    assert "access-qa-portal" in roles
