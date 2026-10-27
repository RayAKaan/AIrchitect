from app.domains.geometry.scene import build_model_scene
from app.domains.model import ArchitecturalModel, Building, Level, Site, Space


def test_scene_has_stable_nodes_mesh_identity_and_bounds() -> None:
    model = ArchitecturalModel(
        project_id="p",
        revision=1,
        site=Site(id="s", width_m=20, depth_m=20),
        buildings=(Building(id="b", name="Main", site_id="s"),),
        levels=(Level(id="l", building_id="b", name="Ground", elevation_m=0, height_m=3),),
        spaces=(Space(id="room", level_id="l", name="Room", boundary=((2,3,0),(6,3,0),(6,7,0),(2,7,0))),),
    )
    scene = build_model_scene(model)
    assert scene.nodes
    assert len(scene.nodes) == len(scene.meshes)
    assert scene.nodes[0].mesh_index == 0
    assert scene.nodes[0].source_model_hash == scene.model_hash
    assert scene.bounds.minimum == (2.0, 3.0, 0.0)
    assert scene.bounds.maximum == (6.0, 7.0, 0.0)
    assert build_model_scene(model) == scene
