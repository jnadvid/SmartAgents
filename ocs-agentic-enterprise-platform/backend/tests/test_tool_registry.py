"""Tests del ToolRegistry: catálogo, autorización y manejo de errores."""
from __future__ import annotations

from app.tools.base import BaseTool, ToolContext
from app.tools.registry import ToolRegistry

EXPECTED_TOOLS = {
    "summarize_text",
    "extract_action_items",
    "generate_markdown_report",
    "search_documents",
    "summarize_document",
    "compare_documents",
    "extract_risks",
    "create_project_plan",
    "create_sales_proposal",
    "analyze_table_text",
    "calculate_basic_financials",
    "review_contract_text",
    "classify_customer_request",
    "parse_wazuh_alert",
    "map_to_mitre_attack",
    "calculate_cvss_priority",
    "generate_compliance_gap",
    "check_prompt_injection_patterns",
    "generate_executive_report",
}


def test_default_registry_has_all_mvp_tools(tool_registry: ToolRegistry) -> None:
    assert set(tool_registry.names()) == EXPECTED_TOOLS


def test_unknown_tool_returns_error_result(tool_registry: ToolRegistry) -> None:
    result = tool_registry.run_tool("tool_inexistente", {})
    assert result.status == "error"
    assert "desconocida" in (result.error_message or "").lower()


def test_unauthorized_tool_is_denied(tool_registry: ToolRegistry) -> None:
    result = tool_registry.run_tool(
        "summarize_text",
        {"text": "hola mundo"},
        ToolContext(agent_name="agente_test"),
        allowed_tools=["extract_risks"],
    )
    assert result.status == "denied"


def test_invalid_input_is_reported_not_raised(tool_registry: ToolRegistry) -> None:
    result = tool_registry.run_tool("summarize_text", {"text": ""}, allowed_tools=["summarize_text"])
    assert result.status == "error"
    assert "inválida" in (result.error_message or "").lower()


def test_tool_timeout_is_handled() -> None:
    import time

    from pydantic import BaseModel

    class _Input(BaseModel):
        pass

    class SlowTool(BaseTool):
        name = "slow_tool"
        category = "test"
        description = "herramienta lenta para test de timeout"
        input_schema = _Input
        timeout_seconds = 1

        def execute(self, payload: _Input, ctx: ToolContext) -> dict:
            time.sleep(3)
            return {"done": True}

    registry = ToolRegistry()
    registry.register(SlowTool())
    result = registry.run_tool("slow_tool", {})
    assert result.status == "timeout"


def test_categories_cover_all_tools(tool_registry: ToolRegistry) -> None:
    categories = tool_registry.categories()
    flattened = {name for names in categories.values() for name in names}
    assert flattened == EXPECTED_TOOLS
