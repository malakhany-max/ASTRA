import astra_security as sec


def test_ground_viewer_can_read_crew_but_cannot_ack_or_issue_commands():
    assert "viewer" in sec.rbac.ROLES
    assert sec.rbac.has_permission("viewer", "read_crew")
    assert sec.rbac.has_permission("viewer", "read_self")
    assert not sec.rbac.has_permission("viewer", "ack_alert")
    assert not sec.rbac.has_permission("viewer", "issue_command")


def test_viewer_role_can_be_authenticated_and_keeps_read_only_permissions():
    sec.rbac.add_user("viewer-1", "local-password", "viewer")
    user = sec.rbac.authenticate("viewer-1", "local-password")
    token = sec.rbac.create_session(user)
    principal = sec.rbac.decode_session(token)
    assert principal["role"] == "viewer"
    assert sec.rbac.has_permission(principal["role"], "read_crew")
    assert not sec.rbac.has_permission(principal["role"], "issue_command")
