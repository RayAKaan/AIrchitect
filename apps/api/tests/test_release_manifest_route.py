from app.main import app


def test_release_manifest_route_is_registered():
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/release-manifest" in {route.path for route in app.routes}
