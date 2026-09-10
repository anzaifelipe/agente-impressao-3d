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
from agente_impressao_3d.domain.models import Vector3
from agente_impressao_3d.domain.orientation import OrientationAnalysisConfiguration
from agente_impressao_3d.domain.overhang import OverhangAnalysisConfiguration
from agente_impressao_3d.domain.print_recommendation import PrintRecommendationConfiguration
from agente_impressao_3d.domain.printer_profile import PrinterProfile
from agente_impressao_3d.domain.scale_and_unit import ScaleAndUnitConfiguration
from agente_impressao_3d.infrastructure.trimesh_face_metrics_reader import (
    TrimeshFaceMetricsReader,
)
from agente_impressao_3d.infrastructure.trimesh_inspector import TrimeshMeshInspector
from agente_impressao_3d.infrastructure.trimesh_triangle_geometry_reader import (
    TrimeshTriangleGeometryReader,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agente-impressao-3d",
        description="Run deterministic STL print analysis and emit a JSON print plan.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="analyze one STL model")
    analyze.add_argument("source", type=Path, help="path to an STL file")
    analyze.add_argument("--printer-manufacturer", required=True)
    analyze.add_argument("--printer-model", required=True)
    analyze.add_argument("--build-volume", nargs=3, type=float, metavar=("X", "Y", "Z"), required=True)
    analyze.add_argument("--build-volume-unit")
    analyze.add_argument("--scale-factor", type=float)
    analyze.add_argument("--physical-unit")
    analyze.add_argument("--overhang-threshold", type=float)
    analyze.add_argument("--batch-size", type=int)
    analyze.add_argument("--max-recommended-overhang", type=float)
    analyze.add_argument("--output", type=Path)
    return parser


def default_use_cases() -> CliUseCases:
    """Wire application cases to infrastructure adapters only at the input edge."""
    return CliUseCases(
        analyze_stl=AnalyzeStl(TrimeshMeshInspector()),
        analyze_scale_and_unit=AnalyzeScaleAndUnit(),
        analyze_build_volume=AnalyzeBuildVolume(),
        analyze_overhang=AnalyzeOverhang(TrimeshFaceMetricsReader()),
        analyze_orientation=AnalyzeOrientation(TrimeshTriangleGeometryReader()),
        analyze_print_recommendation=AnalyzePrintRecommendation(),
        analyze_print_plan=AnalyzePrintPlan(),
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
        _validate_source(args.source)
        plan = _execute_analysis(args, use_cases or default_use_cases())
        payload = plan.to_dict()
        if args.output is None:
            json.dump(payload, output_stream, indent=2)
            output_stream.write("\n")
        else:
            with args.output.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
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
    profile_options: dict[str, object] = {
        "manufacturer": args.printer_manufacturer,
        "model": args.printer_model,
        "build_volume": Vector3(*args.build_volume),
    }
    if args.build_volume_unit is not None:
        profile_options["build_volume_unit"] = args.build_volume_unit
    printer_profile = PrinterProfile(**profile_options)
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


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
