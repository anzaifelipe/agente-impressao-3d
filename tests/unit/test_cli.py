import io
import json
from pathlib import Path

import pytest

from agente_impressao_3d.cli.main import CliUseCases, build_parser, run
from agente_impressao_3d.domain.models import Vector3


class FakeCase:
    def __init__(self, result: object, calls: list[tuple[object, ...]]) -> None:
        self.result = result
        self.calls = calls

    def execute(self, *args: object, **kwargs: object) -> object:
        self.calls.append(args)
        return self.result


class FakePlan:
    def to_dict(self) -> dict[str, object]:
        return {"schema_version": "1.0", "source": {"path": "model.stl"}, "analyses": {}}


class FakeOverhang:
    def to_dict(self) -> dict[str, object]:
        return {"schema_version": "1.0", "facts": {"overhang_face_count": 0}}


def fake_use_cases(calls: list[tuple[object, ...]]) -> CliUseCases:
    stl, scale, build, orientation, recommendation, plan = (object() for _ in range(6))
    overhang = FakeOverhang()
    return CliUseCases(
        FakeCase(stl, calls), FakeCase(scale, calls), FakeCase(build, calls),
        FakeCase(overhang, calls), FakeCase(orientation, calls),
        FakeCase(recommendation, calls), FakeCase(FakePlan(), calls),
    )


def arguments(source: Path, *extra: str) -> list[str]:
    return [
        "analyze", str(source), "--printer-manufacturer", "Bambu Lab", "--printer-model", "A1 Mini",
        "--build-volume", "180", "180", "180", *extra,
    ]


def test_parser_and_cli_build_configs_run_full_flow_and_write_json(tmp_path: Path) -> None:
    source = tmp_path / "model.stl"
    source.touch()
    calls: list[tuple[object, ...]] = []
    stdout = io.StringIO()
    code = run(
        arguments(
            source, "--build-volume-unit", "mm", "--scale-factor", "100",
            "--physical-unit", "mm", "--overhang-threshold", "30", "--batch-size", "10",
            "--max-recommended-overhang", "25",
        ),
        use_cases=fake_use_cases(calls), stdout=stdout, stderr=io.StringIO(),
    )

    assert code == 0
    assert json.loads(stdout.getvalue())["analyses"]["overhang"]["facts"] == {
        "overhang_face_count": 0
    }
    scale_configuration = calls[1][1]
    printer_profile = calls[2][1]
    overhang_configuration = calls[3][1]
    orientation_configuration = calls[4][2]
    recommendation_configuration = calls[5][2]
    assert scale_configuration.scale_factor == 100
    assert printer_profile.model == "A1 Mini"
    assert printer_profile.build_volume == Vector3(180.0, 180.0, 180.0)
    assert overhang_configuration.threshold_degrees == 30
    assert overhang_configuration.batch_size == 10
    assert orientation_configuration.scale_and_unit is scale_configuration
    assert recommendation_configuration.maximum_recommended_overhang_area_percentage == 25


def test_output_option_saves_json_without_mixing_json_into_stdout(tmp_path: Path) -> None:
    source = tmp_path / "model.stl"
    destination = tmp_path / "result.json"
    source.touch()
    stdout = io.StringIO()

    code = run(
        arguments(source, "--output", str(destination)),
        use_cases=fake_use_cases([]), stdout=stdout, stderr=io.StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == ""
    assert json.loads(destination.read_text())["analyses"]["overhang"]["facts"] == {
        "overhang_face_count": 0
    }


def test_reports_missing_source_and_invalid_build_volume_as_expected_errors(tmp_path: Path) -> None:
    stderr = io.StringIO()
    missing = run(
        arguments(tmp_path / "missing.stl"), use_cases=fake_use_cases([]), stderr=stderr
    )
    assert missing == 2
    assert "was not found" in stderr.getvalue()

    source = tmp_path / "model.stl"
    source.touch()
    stderr = io.StringIO()
    invalid_arguments = arguments(source)
    invalid_arguments[invalid_arguments.index("180")] = "0"
    invalid = run(
        invalid_arguments,
        use_cases=fake_use_cases([]), stderr=stderr,
    )
    assert invalid == 2
    assert "build_volume" in stderr.getvalue()


def test_parser_requires_analyze_arguments() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["analyze"])
