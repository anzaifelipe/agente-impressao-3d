"""Argparse input adapter for composing the deterministic print-analysis flow."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO

from agente_impressao_3d.application.analyze_build_volume import AnalyzeBuildVolume
from agente_impressao_3d.application.analyze_orientation import AnalyzeOrientation
from agente_impressao_3d.application.analyze_overhang import AnalyzeOverhang
from agente_impressao_3d.application.analyze_print_plan import AnalyzePrintPlan
from agente_impressao_3d.application.analyze_print_recommendation import (
    AnalyzePrintRecommendation,
)
from agente_impressao_3d.application.analyze_scale_and_unit import AnalyzeScaleAndUnit
from agente_impressao_3d.application.analyze_stl import AnalyzeStl
from agente_impressao_3d.application.get_printer_profile import GetPrinterProfile
from agente_impressao_3d.application.list_printer_profiles import ListPrinterProfiles
from agente_impressao_3d.application.summarize_print_plan import SummarizePrintPlan
from agente_impressao_3d.domain.models import Vector3
from agente_impressao_3d.domain.orientation import OrientationAnalysisConfiguration
from agente_impressao_3d.domain.overhang import OverhangAnalysisConfiguration
from agente_impressao_3d.domain.print_recommendation import PrintRecommendationConfiguration
from agente_impressao_3d.domain.printer_profile import PrinterProfile, PrinterProfileEntry
from agente_impressao_3d.domain.scale_and_unit import ScaleAndUnitConfiguration
from agente_impressao_3d.domain.print_plan_summary import PrintPlanSummaryResult
from agente_impressao_3d.infrastructure.trimesh_face_metrics_reader import (
    TrimeshFaceMetricsReader,
)
from agente_impressao_3d.infrastructure.trimesh_inspector import TrimeshMeshInspector
from agente_impressao_3d.infrastructure.trimesh_triangle_geometry_reader import (
    TrimeshTriangleGeometryReader,
)
from agente_impressao_3d.infrastructure.built_in_printer_profiles import (
    BuiltInPrinterProfileReader,
)


class Executable(Protocol):
    def execute(self, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True, slots=True)
class CliUseCases:
    """Dependencies assembled at the CLI boundary and replaceable by test fakes."""

    analyze_stl: Executable
    analyze_scale_and_unit: Executable
    analyze_build_volume: Executable
    analyze_overhang: Executable
    analyze_orientation: Executable
    analyze_print_recommendation: Executable
    analyze_print_plan: Executable
    summarize_print_plan: Executable
    get_printer_profile: Executable
    list_printer_profiles: Executable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agente-impressao-3d",
        description="Run deterministic STL print analysis.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("printers", help="list available reusable printer profiles")
    analyze = subparsers.add_parser("analyze", help="analyze one STL model")
    analyze.add_argument("source", type=Path, help="path to an STL file")
    analyze.add_argument("--printer", help="stable identifier of a built-in printer profile")
    analyze.add_argument("--printer-manufacturer")
    analyze.add_argument("--printer-model")
    analyze.add_argument("--build-volume", nargs=3, type=float, metavar=("X", "Y", "Z"))
    analyze.add_argument("--build-volume-unit")
    analyze.add_argument("--scale-factor", type=float)
    analyze.add_argument("--physical-unit")
    analyze.add_argument("--overhang-threshold", type=float)
    analyze.add_argument("--batch-size", type=int)
    analyze.add_argument("--max-recommended-overhang", type=float)
    analyze.add_argument("--json", action="store_true", help="write the full technical print plan as JSON to stdout")
    analyze.add_argument("--output", type=Path)
    return parser


def default_use_cases() -> CliUseCases:
    """Wire application cases to infrastructure adapters only at the input edge."""
    profile_reader = BuiltInPrinterProfileReader()
    return CliUseCases(
        analyze_stl=AnalyzeStl(TrimeshMeshInspector()),
        analyze_scale_and_unit=AnalyzeScaleAndUnit(),
        analyze_build_volume=AnalyzeBuildVolume(),
        analyze_overhang=AnalyzeOverhang(TrimeshFaceMetricsReader()),
        analyze_orientation=AnalyzeOrientation(TrimeshTriangleGeometryReader()),
        analyze_print_recommendation=AnalyzePrintRecommendation(),
        analyze_print_plan=AnalyzePrintPlan(),
        summarize_print_plan=SummarizePrintPlan(),
        get_printer_profile=GetPrinterProfile(profile_reader),
        list_printer_profiles=ListPrinterProfiles(profile_reader),
    )


def run(
    argv: list[str] | None = None,
    *,
    use_cases: CliUseCases | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the CLI, returning a conventional process exit code for expected errors."""
    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr
    args = build_parser().parse_args(argv)
    try:
        active_use_cases = use_cases or default_use_cases()
        if args.command == "printers":
            output_stream.write(
                format_printer_profiles(active_use_cases.list_printer_profiles.execute())
            )
            return 0
        if args.json and args.output is not None:
            raise ValueError("--json and --output cannot be used together")
        _validate_source(args.source)
        plan = _execute_analysis(args, active_use_cases)
        if args.json:
            json.dump(plan.to_dict(), output_stream, indent=2)
            output_stream.write("\n")
        elif args.output is not None:
            payload = plan.to_dict()
            with args.output.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
            summary = active_use_cases.summarize_print_plan.execute(plan)
            output_stream.write(_format_saved_result(summary, args.output))
        else:
            summary = active_use_cases.summarize_print_plan.execute(plan)
            output_stream.write(format_print_plan_summary(summary))
        return 0
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=error_stream)
        return 2


def _validate_source(source: Path) -> None:
    if source.suffix.lower() != ".stl":
        raise ValueError("source file must use the .stl extension.")
    if not source.is_file():
        raise ValueError(f"source file was not found: {source}")


def _execute_analysis(args: argparse.Namespace, use_cases: CliUseCases) -> object:
    scale_defaults = ScaleAndUnitConfiguration()
    scale_configuration = ScaleAndUnitConfiguration(
        scale_factor=(args.scale_factor if args.scale_factor is not None else scale_defaults.scale_factor),
        physical_unit=(args.physical_unit if args.physical_unit is not None else scale_defaults.physical_unit),
    )
    overhang_defaults = OverhangAnalysisConfiguration()
    overhang_configuration = OverhangAnalysisConfiguration(
        threshold_degrees=(args.overhang_threshold if args.overhang_threshold is not None else overhang_defaults.threshold_degrees),
        batch_size=(args.batch_size if args.batch_size is not None else overhang_defaults.batch_size),
    )
    orientation_configuration = OrientationAnalysisConfiguration(
        threshold_degrees=overhang_configuration.threshold_degrees,
        batch_size=overhang_configuration.batch_size,
        scale_and_unit=scale_configuration,
    )
    printer_profile = _resolve_printer_profile(args, use_cases)
    recommendation_configuration = PrintRecommendationConfiguration(
        maximum_recommended_overhang_area_percentage=args.max_recommended_overhang
    )

    stl = use_cases.analyze_stl.execute(args.source)
    scale = use_cases.analyze_scale_and_unit.execute(stl, scale_configuration)
    build_volume = use_cases.analyze_build_volume.execute(scale, printer_profile)
    overhang = use_cases.analyze_overhang.execute(args.source, overhang_configuration)
    orientation = use_cases.analyze_orientation.execute(
        args.source, printer_profile, orientation_configuration
    )
    recommendation = use_cases.analyze_print_recommendation.execute(stl, orientation, recommendation_configuration)
    plan = use_cases.analyze_print_plan.execute(
        stl, scale, build_volume, overhang, orientation, recommendation
    )
    return plan


def _resolve_printer_profile(
    args: argparse.Namespace, use_cases: CliUseCases
) -> PrinterProfile:
    manual_values = (
        args.printer_manufacturer,
        args.printer_model,
        args.build_volume,
        args.build_volume_unit,
    )
    has_manual_values = any(value is not None for value in manual_values)
    if args.printer is not None:
        if has_manual_values:
            raise ValueError(
                "--printer cannot be combined with manual printer profile arguments"
            )
        return use_cases.get_printer_profile.execute(args.printer)

    if not all(
        value is not None
        for value in (args.printer_manufacturer, args.printer_model, args.build_volume)
    ):
        raise ValueError(
            "provide --printer or manual --printer-manufacturer, --printer-model, "
            "and --build-volume arguments"
        )
    profile_options: dict[str, object] = {
        "manufacturer": args.printer_manufacturer,
        "model": args.printer_model,
        "build_volume": Vector3(*args.build_volume),
    }
    if args.build_volume_unit is not None:
        profile_options["build_volume_unit"] = args.build_volume_unit
    return PrinterProfile(**profile_options)


def format_printer_profiles(entries: tuple[PrinterProfileEntry, ...]) -> str:
    """Render the already resolved profile entries for terminal users."""
    lines = ["Available printer profiles:"]
    for entry in entries:
        profile = entry.profile
        volume = profile.build_volume
        lines.extend(
            [
                "",
                entry.profile_id,
                f"  Manufacturer: {profile.manufacturer}",
                f"  Model: {profile.model}",
                (
                    "  Build volume: "
                    f"{volume.x:g} × {volume.y:g} × {volume.z:g} "
                    f"{profile.build_volume_unit}"
                ),
            ]
        )
    return "\n".join(lines) + "\n"


def format_print_plan_summary(summary: PrintPlanSummaryResult) -> str:
    """Render a compact presentation result without interpreting the print plan."""
    facts = summary.facts
    dimensions = facts.physical_dimensions
    fit = _format_fit(facts.fits_build_volume)
    orientation = facts.recommended_orientation or "Nenhuma"
    height = (
        f"{facts.print_height:.2f} {facts.physical_unit}"
        if facts.print_height is not None
        else "Não disponível"
    )
    overhang = (
        f"{facts.overhang_area_percentage:.2f}%"
        if facts.overhang_area_percentage is not None
        else "Não calculável"
    )
    lines = [
        "Análise concluída",
        "",
        "Modelo:",
        summary.source_path,
        "",
        "Status:",
        facts.recommendation_status.upper(),
        "",
        "Dimensões:",
        (
            f"{dimensions.x:.2f} × {dimensions.y:.2f} × {dimensions.z:.2f} "
            f"{facts.physical_unit}"
        ),
        "",
        "Cabe no volume de impressão:",
        fit,
        "",
        "Orientação recomendada:",
        orientation,
        "",
        "Altura de impressão:",
        height,
        "",
        "Área de overhang:",
        overhang,
        "",
        "Avisos:",
    ]
    if not summary.warnings:
        lines.append("Nenhum")
    else:
        for warning in summary.warnings:
            lines.extend(
                [
                    f"- [{warning.severity}] {warning.code}",
                    f"  {warning.message}",
                    f"  Origem: {warning.origin}",
                ]
            )
    return "\n".join(lines) + "\n"


def _format_saved_result(summary: PrintPlanSummaryResult, destination: Path) -> str:
    return (
        "Análise concluída\n\n"
        "Resultado técnico salvo em:\n"
        f"{destination}\n\n"
        "Status:\n"
        f"{summary.facts.recommendation_status.upper()}\n"
    )


def _format_fit(fits: bool | None) -> str:
    if fits is None:
        return "NÃO DISPONÍVEL"
    return "SIM" if fits else "NÃO"


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
