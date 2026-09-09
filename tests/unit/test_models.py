from agente_impressao_3d.domain.models import Volume


def test_volume_reliability_requires_a_matching_value() -> None:
    assert Volume(cubic_units=None, reliable=False).reliable is False


def test_reliable_volume_requires_a_value() -> None:
    try:
        Volume(cubic_units=None, reliable=True)
    except ValueError as error:
        assert "reliable volume" in str(error).lower()
    else:
        raise AssertionError("Expected inconsistent volume to be rejected")
