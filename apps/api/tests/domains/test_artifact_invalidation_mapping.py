from app.domains.commands.artifact_invalidation import GROUP_TO_ARTIFACT_TYPE


def test_program_impact_group_targets_the_persisted_program_artifact_type():
    assert GROUP_TO_ARTIFACT_TYPE["program"] == "architectural_program"


def test_every_impact_group_has_a_non_empty_artifact_type():
    assert GROUP_TO_ARTIFACT_TYPE
    assert all(group and artifact_type for group, artifact_type in GROUP_TO_ARTIFACT_TYPE.items())


def test_impact_group_mapping_is_unique_by_group():
    assert len(GROUP_TO_ARTIFACT_TYPE) == len(set(GROUP_TO_ARTIFACT_TYPE))
