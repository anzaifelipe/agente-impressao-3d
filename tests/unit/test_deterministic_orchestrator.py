from pathlib import Path

from agente_impressao_3d.orchestration import (
    DeterministicOrchestrator,
    OrchestrationRequest,
)
from agente_impressao_3d.tools.registry import build_tools, default_tool_services


def orchestrator(tmp_path: Path) -> DeterministicOrchestrator:
    tools = build_tools(default_tool_services(tmp_path / "config.json"))
    return DeterministicOrchestrator(tools)


def test_lists_printer_profiles_through_mapped_tool(tmp_path: Path) -> None:
    result = orchestrator(tmp_path).execute(
        OrchestrationRequest("list_printer_profiles", {})
    )

    assert result.to_dict()["ok"] is True
    assert result.tool == "list_printer_profiles"
    assert result.result["profiles"][0]["profile_id"] == "bambu-lab-a1-mini"


def test_get_configuration_preserves_action_and_tool_observation(tmp_path: Path) -> None:
    result = orchestrator(tmp_path).execute(
        OrchestrationRequest("get_configuration", {})
    )

    assert result.ok is False
    assert result.action == "get_configuration"
    assert result.tool == "get_cli_configuration"
    assert result.error["code"] == "CLI_CONFIGURATION_NOT_FOUND"


def test_sets_valid_profile_and_preserves_tool_error_for_unknown_profile(
    tmp_path: Path,
) -> None:
    instance = orchestrator(tmp_path)
    success = instance.execute(
        OrchestrationRequest(
            "set_default_printer_profile",
            {"profile_id": "bambu-lab-a1-mini"},
        )
    )
    failure = instance.execute(
        OrchestrationRequest(
            "set_default_printer_profile", {"profile_id": "unknown"}
        )
    )

    assert success.ok is True
    assert success.tool == "set_default_printer_profile"
    assert success.result["default_printer_profile"] == "bambu-lab-a1-mini"
    assert failure.ok is False
    assert failure.tool == "set_default_printer_profile"
    assert failure.error["code"] == "UNKNOWN_PRINTER_PROFILE"


def test_analyzes_fixture_with_the_analyze_model_intent(tmp_path: Path) -> None:
    result = orchestrator(tmp_path).execute(
        OrchestrationRequest(
            "analyze_model",
            {
                "path": "tests/fixtures/cube_ascii.stl",
                "printer_profile": "bambu-lab-a1-mini",
                "batch_size": 10,
            },
        )
    )

    assert result.ok is True
    assert result.action == "analyze_model"
    assert result.tool == "analyze_print_plan"
    assert "analyses" in result.result


def test_unknown_action_does_not_select_a_tool(tmp_path: Path) -> None:
    result = orchestrator(tmp_path).execute(
        OrchestrationRequest("unknown_action", {})
    )

    assert result.to_dict() == {
        "ok": False,
        "action": "unknown_action",
        "error": {
            "code": "UNKNOWN_ACTION",
            "message": "Unknown orchestration action: unknown_action",
        },
    }


def test_invalid_arguments_preserve_the_tool_layer_error(tmp_path: Path) -> None:
    result = orchestrator(tmp_path).execute(
        OrchestrationRequest("analyze_model", {})
    )

    assert result.ok is False
    assert result.tool == "analyze_print_plan"
    assert result.error["code"] == "INVALID_TOOL_ARGUMENTS"
