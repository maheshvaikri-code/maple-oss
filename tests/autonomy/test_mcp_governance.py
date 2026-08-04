"""Tests for register_mcp_tools governance hooks (policy, namespace, cap, sanitize).

MAPLE improvement #2 (proposed; revalidate with owner). MCP tools are an UNTRUSTED external
surface; these opt-in hooks let a host mediate that trust boundary at registration -- so a
host does not have to re-implement (and, as we saw downstream, get wrong) default-deny
classification, server-namespacing, name sanitization, and a flood cap.
"""

from maple.autonomy.mcp_tools import register_mcp_tools, sanitize_tool_name
from maple.autonomy.tools import Tool, ToolRegistry
from maple.core.result import Result


def _tool(name, description="", requires_approval=False):
    return Tool(
        name=name,
        description=description,
        parameters={},
        handler=lambda **k: Result.ok("x"),
        requires_approval=requires_approval,
        tags=["mcp"],
    )


class TestSanitize:
    def test_strips_control_and_unsafe_chars(self):
        s = sanitize_tool_name("evil\n foo\t/../bar!")
        for bad in ("\n", " ", "\t", "/", "!"):
            assert bad not in s
        assert "foo" in s and "bar" in s

    def test_bounds_length(self):
        assert len(sanitize_tool_name("x" * 500, max_len=10)) == 10
        assert sanitize_tool_name(None) == ""


class TestPolicy:
    def test_policy_reject_skips_registration(self):
        reg = ToolRegistry()
        n = register_mcp_tools(reg, [_tool("a"), _tool("b")], policy=lambda t, s: t.name == "a")
        assert n == 1
        assert reg.get("a").is_ok() and reg.get("b").is_err()

    def test_policy_raising_fails_closed_and_rejects(self):
        reg = ToolRegistry()

        def boom(t, s):
            raise RuntimeError("hostile policy input")

        n = register_mcp_tools(reg, [_tool("a")], policy=boom)
        assert n == 0 and reg.get("a").is_err()

    def test_default_no_policy_registers_all_backward_compat(self):
        reg = ToolRegistry()
        assert register_mcp_tools(reg, [_tool("a"), _tool("b")]) == 2

    def test_policy_receives_server_id(self):
        reg = ToolRegistry()
        seen = {}

        def pol(t, s):
            seen["sid"] = s
            return True

        register_mcp_tools(reg, [_tool("a")], server_id="srv-1", policy=pol)
        assert seen["sid"] == "srv-1"


class TestNamespace:
    def test_namespaced_names_prevent_native_shadowing(self):
        reg = ToolRegistry()
        register_mcp_tools(reg, [_tool("repo.write")], server_id="srvA", namespace=True)
        assert reg.get("mcp.srvA.repo.write").is_ok()
        assert reg.get("repo.write").is_err()  # never the bare native-looking name

    def test_two_servers_same_toolname_are_distinct(self):
        reg = ToolRegistry()
        register_mcp_tools(reg, [_tool("list")], server_id="A", namespace=True)
        register_mcp_tools(reg, [_tool("list")], server_id="B", namespace=True)
        assert reg.get("mcp.A.list").is_ok() and reg.get("mcp.B.list").is_ok()

    def test_namespace_without_server_id_registers_nothing(self):
        reg = ToolRegistry()
        assert register_mcp_tools(reg, [_tool("a")], namespace=True) == 0  # fail-closed

    def test_namespace_sanitizes_a_hostile_name(self):
        reg = ToolRegistry()
        register_mcp_tools(reg, [_tool("ev\nil spoof")], server_id="s", namespace=True)
        assert all("\n" not in k and " " not in k for k in reg._tools)


class TestCap:
    def test_max_tools_caps_registration(self):
        reg = ToolRegistry()
        n = register_mcp_tools(reg, [_tool(f"t{i}") for i in range(50)], max_tools=10)
        assert n == 10
