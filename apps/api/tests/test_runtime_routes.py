from app.main import app


def test_runtime_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/health" in paths
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/release-readiness" in paths
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/release-manifest" in paths
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/release-package" in paths
    assert "/api/v1/organizations/{organization_id}/runtime/metrics" in paths
