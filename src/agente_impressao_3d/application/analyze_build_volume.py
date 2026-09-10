"""Use case for comparing scaled part dimensions with a printer build volume."""

from dataclasses import dataclass

from agente_impressao_3d.domain.build_volume import (
    BuildVolumeAnalysisAssumptions,
    BuildVolumeAnalysisResult,
    BuildVolumeFacts,
)
from agente_impressao_3d.domain.models import AnalysisWarning, Vector3
from agente_impressao_3d.domain.printer_profile import PrinterProfile
from agente_impressao_3d.domain.scale_and_unit import ScaleAndUnitAnalysisResult


@dataclass(frozen=True, slots=True)
class AnalyzeBuildVolume:
    """Checks the supplied orientation without reading or transforming the STL."""

    def execute(
        self,
        scale_and_unit_analysis: ScaleAndUnitAnalysisResult,
        printer_profile: PrinterProfile,
        assumptions: BuildVolumeAnalysisAssumptions | None = None,
    ) -> BuildVolumeAnalysisResult:
        physical_unit = scale_and_unit_analysis.configuration.physical_unit
        if printer_profile.build_volume_unit != physical_unit:
            raise ValueError(
                "printer_profile.build_volume_unit must match "
                "scale_and_unit_analysis.configuration.physical_unit."
            )

        dimensions = scale_and_unit_analysis.facts.physical_dimensions
        build_volume = printer_profile.build_volume
        fits_x = dimensions.x <= build_volume.x
        fits_y = dimensions.y <= build_volume.y
        fits_z = dimensions.z <= build_volume.z
        fits = fits_x and fits_y and fits_z

        remaining_space = Vector3(
            x=max(build_volume.x - dimensions.x, 0.0),
            y=max(build_volume.y - dimensions.y, 0.0),
            z=max(build_volume.z - dimensions.z, 0.0),
        )
        overflow = Vector3(
            x=max(dimensions.x - build_volume.x, 0.0),
            y=max(dimensions.y - build_volume.y, 0.0),
            z=max(dimensions.z - build_volume.z, 0.0),
        )

        warnings: list[AnalysisWarning] = []
        if not fits:
            exceeded_axes = ", ".join(
                axis
                for axis, axis_fits in (("X", fits_x), ("Y", fits_y), ("Z", fits_z))
                if not axis_fits
            )
            warnings.append(
                AnalysisWarning(
                    code="MODEL_EXCEEDS_BUILD_VOLUME",
                    message=f"Model exceeds the printer build volume on axis or axes: {exceeded_axes}.",
                )
            )

        return BuildVolumeAnalysisResult(
            source_path=scale_and_unit_analysis.source_path,
            printer_profile=printer_profile,
            facts=BuildVolumeFacts(
                physical_dimensions=dimensions,
                fits=fits,
                fits_x=fits_x,
                fits_y=fits_y,
                fits_z=fits_z,
                remaining_space=remaining_space,
                overflow=overflow,
            ),
            assumptions=assumptions or BuildVolumeAnalysisAssumptions(),
            warnings=tuple(warnings),
        )
