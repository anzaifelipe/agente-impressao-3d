import io
import json
from pathlib import Path

import pytest

from agente_impressao_3d.cli.main import CliUseCases, build_parser, run
from agente_impressao_3d.domain.models import Vector3
from agente_impressao_3d.domain.printer_profile import PrinterProfile, PrinterProfileEntry
from agente_impressao_3d.domain.print_plan_summary import (
    PrintPlanSummaryFacts,
    PrintPlanSummaryResult,
    PrintPlanSummaryWarning,
)


class FakeCase:
    def __init__(self, result: object, calls: list[tuple[object, ...]]) -> None:
        self.result = result
        self.calls = calls

    def execute(self, *args: object, **kwargs: object) -> object:
        self.calls.append(args)
        return self.result


class FailingCase:
    def __init__(self, error: Exception, calls: list[tuple[object, ...]]) -> None:
        self.error = error
        self.calls = calls

    def execute(self, *args: object, **kwargs: object) -> object:
        self.calls.append(args)
        raise self.error


class FakePlan:
    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "source": {"path": "model.stl"},
            "analyses": {"overhang": {"facts": {"overhang_face_count": 0}}},
        }


def summary(
    *,
    overhang: float | None = 21.83,
    orientation: str | None = "negative_z",
    warnings: tuple[PrintPlanSummaryWarning, ...] = (),
) -> PrintPlanSummaryResult:
    return PrintPlanSummaryResult(
        "model.stl",
        PrintPlanSummaryFacts(
            Vector3(88.5, 100, 31.4), "mm", True, orientation,
            31.4 if orientation else None, overhang, "recommended", len(warnings),
        ),
        warnings,
    )


def fake_use_cases(
    calls: list[tuple[object, ...]], result_summary: PrintPlanSummaryResult | None = None,
    profile: PrinterProfile | None = None,
) -> CliUseCases:
    stl, scale, build, overhang, orientation, recommendation = (
        object() for _ in range(6)
    )
    return CliUseCases(
        FakeCase(stl, calls), FakeCase(scale, calls), FakeCase(build, calls),
        FakeCase(overhang, calls), FakeCase(orientation, calls),
        FakeCase(recommendation, calls), FakeCase(FakePlan(), calls),
        FakeCase(result_summary or summary(), calls),
        FakeCase(profile or PrinterProfile("Bambu Lab", "A1 Mini", Vector3(180, 180, 180)), calls),
        FakeCase((PrinterProfileEntry("bambu-lab-a1-mini", PrinterProfile("Bambu Lab", "A1 Mini", Vector3(180, 180, 180))),), calls),
    )


def arguments(source: Path, *extra: str) -> list[str]:
    return [
        "analyze", str(source), "--printer-manufacturer", "Bambu Lab",
        "--printer-model", "A1 Mini", "--build-volume", "180", "180", "180",
        *extra,
    ]


def profile_arguments(source: Path, *extra: str) -> list[str]:
    return [
        "analyze", str(source), "--printer", "bambu-lab-a1-mini", *extra,
    ]


def test_default_output_uses_summary_and_renders_human_readable_text(
    tmp_path: Path,
) -> None:
    source = tmp_path / "model.stl"
    source.touch()
    calls: list[tuple[object, ...]] = []
    stdout = io.StringIO()
    warning = PrintPlanSummaryWarning(
        "NORMAL_ORIENTATION_UNVERIFIED", "Normals were not verified.",
        "warning", "overhang_analysis",
    )

    code = run(
        arguments(source),
        use_cases=fake_use_cases(calls, summary(warnings=(warning,))),
        stdout=stdout,
        stderr=io.StringIO(),
    )

    rendered = stdout.getvalue()
    assert code == 0
    assert "RECOMMENDED" in rendered
    assert "88.50 × 100.00 × 31.40 mm" in rendered
    assert "SIM" in rendered
    assert "negative_z" in rendered
    assert "21.83%" in rendered
    assert "[warning] NORMAL_ORIENTATION_UNVERIFIED" in rendered
    assert "Normals were not verified." in rendered
    assert len(calls) == 8


def test_json_writes_full_technical_plan_without_summary(tmp_path: Path) -> None:
    source = tmp_path / "model.stl"
    source.touch()
    calls: list[tuple[object, ...]] = []
    stdout = io.StringIO()

    code = run(
        arguments(source, "--json"), use_cases=fake_use_cases(calls),
        stdout=stdout, stderr=io.StringIO(),
    )

    assert code == 0
    assert json.loads(stdout.getvalue())["analyses"]["overhang"]["facts"] == {
        "overhang_face_count": 0
    }
    assert len(calls) == 7


def test_output_saves_full_plan_and_prints_short_human_confirmation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "model.stl"
    destination = tmp_path / "result.json"
    source.touch()
    stdout = io.StringIO()

    code = run(
        arguments(source, "--output", str(destination)),
        use_cases=fake_use_cases([]), stdout=stdout, stderr=io.StringIO(),
    )

    assert code == 0
    assert json.loads(destination.read_text())["analyses"]["overhang"]["facts"] == {
        "overhang_face_count": 0
    }
    assert "Resultado técnico salvo em:" in stdout.getvalue()
    assert "RECOMMENDED" in stdout.getvalue()
    assert '"analyses"' not in stdout.getvalue()


def test_rejects_json_and_output_without_executing_analyses(tmp_path: Path) -> None:
    source = tmp_path / "model.stl"
    source.touch()
    calls: list[tuple[object, ...]] = []
    stderr = io.StringIO()

    code = run(
        arguments(source, "--json", "--output", str(tmp_path / "result.json")),
        use_cases=fake_use_cases(calls), stdout=io.StringIO(), stderr=stderr,
    )

    assert code == 2
    assert "--json and --output cannot be used together" in stderr.getvalue()
    assert calls == []


def test_renders_unavailable_overhang_no_orientation_and_no_warnings(
    tmp_path: Path,
) -> None:
    source = tmp_path / "model.stl"
    source.touch()
    stdout = io.StringIO()

    code = run(
        arguments(source),
        use_cases=fake_use_cases([], summary(overhang=None, orientation=None)),
        stdout=stdout, stderr=io.StringIO(),
    )

    assert code == 0
    assert "Não calculável" in stdout.getvalue()
    assert "Nenhuma" in stdout.getvalue()
    assert "Avisos:\nNenhum" in stdout.getvalue()


def test_printers_lists_built_in_entries_from_the_list_use_case() -> None:
    calls: list[tuple[object, ...]] = []
    stdout = io.StringIO()

    code = run(
        ["printers"], use_cases=fake_use_cases(calls),
        stdout=stdout, stderr=io.StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == (
        "Available printer profiles:\n\n"
        "bambu-lab-a1-mini\n"
        "  Manufacturer: Bambu Lab\n"
        "  Model: A1 Mini\n"
        "  Build volume: 180 × 180 × 180 mm\n"
    )
    assert calls == [()]


def test_analyze_with_known_profile_resolves_it_before_the_pipeline(
    tmp_path: Path,
) -> None:
    source = tmp_path / "model.stl"
    source.touch()
    calls: list[tuple[object, ...]] = []

    code = run(
        profile_arguments(source, "--json"), use_cases=fake_use_cases(calls),
        stdout=io.StringIO(), stderr=io.StringIO(),
    )

    assert code == 0
    assert calls[0] == ("bambu-lab-a1-mini",)
    assert calls[3][1] == PrinterProfile(
        "Bambu Lab", "A1 Mini", Vector3(180, 180, 180)
    )


def test_unknown_profile_reports_error_without_running_analysis(tmp_path: Path) -> None:
    source = tmp_path / "model.stl"
    source.touch()
    calls: list[tuple[object, ...]] = []
    use_cases = fake_use_cases(calls)
    use_cases = CliUseCases(
        *(
            getattr(use_cases, field)
            for field in (
                "analyze_stl", "analyze_scale_and_unit", "analyze_build_volume",
                "analyze_overhang", "analyze_orientation", "analyze_print_recommendation",
                "analyze_print_plan", "summarize_print_plan",
            )
        ),
        FailingCase(ValueError("unknown printer profile: missing-printer"), calls),
        use_cases.list_printer_profiles,
    )
    stderr = io.StringIO()

    code = run(
        ["analyze", str(source), "--printer", "missing-printer"],
        use_cases=use_cases, stdout=io.StringIO(), stderr=stderr,
    )

    assert code == 2
    assert "unknown printer profile: missing-printer" in stderr.getvalue()
    assert calls == [("missing-printer",)]


def test_rejects_profile_and_manual_arguments_without_running_analysis(
    tmp_path: Path,
) -> None:
    source = tmp_path / "model.stl"
    source.touch()
    calls: list[tuple[object, ...]] = []
    stderr = io.StringIO()

    code = run(
        profile_arguments(source, "--build-volume", "200", "200", "200"),
        use_cases=fake_use_cases(calls), stdout=io.StringIO(), stderr=stderr,
    )

    assert code == 2
    assert "--printer cannot be combined" in stderr.getvalue()
    assert calls == []


def test_requires_a_known_or_complete_manual_printer_profile(tmp_path: Path) -> None:
    source = tmp_path / "model.stl"
    source.touch()
    calls: list[tuple[object, ...]] = []
    stderr = io.StringIO()

    code = run(
        ["analyze", str(source)], use_cases=fake_use_cases(calls),
        stdout=io.StringIO(), stderr=stderr,
    )

    assert code == 2
    assert "provide --printer or manual" in stderr.getvalue()
    assert calls == []


def test_parser_and_cli_build_configs_run_full_flow(tmp_path: Path) -> None:
    source = tmp_path / "model.stl"
    source.touch()
    calls: list[tuple[object, ...]] = []
    use_cases = fake_use_cases(calls)
    code = run(
        arguments(
            source, "--json", "--build-volume-unit", "mm", "--scale-factor",
            "100", "--physical-unit", "mm", "--overhang-threshold", "30",
            "--batch-size", "10", "--max-recommended-overhang", "25",
        ),
        use_cases=use_cases, stdout=io.StringIO(), stderr=io.StringIO(),
    )

    assert code == 0
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
    assert calls[6][3] is use_cases.analyze_overhang.result


def test_reports_missing_source_and_invalid_build_volume_as_expected_errors(
    tmp_path: Path,
) -> None:
    stderr = io.StringIO()
    missing = run(
        arguments(tmp_path / "missing.stl"), use_cases=fake_use_cases([]), stderr=stderr,
    )
    assert missing == 2
    assert "was not found" in stderr.getvalue()

    source = tmp_path / "model.stl"
    source.touch()
    stderr = io.StringIO()
    invalid_arguments = arguments(source)
    invalid_arguments[invalid_arguments.index("180")] = "0"
    invalid = run(
        invalid_arguments, use_cases=fake_use_cases([]), stderr=stderr,
    )
    assert invalid == 2
    assert "build_volume" in stderr.getvalue()


def test_parser_requires_analyze_arguments() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["analyze"])
