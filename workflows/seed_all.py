"""Run all 13 workflow seed scripts against the running backend."""
from seed_condition_router import seed as seed_condition
from seed_data_pipeline    import seed as seed_pipeline
from seed_remote_agent     import seed as seed_remote
from seed_orchestrator     import seed as seed_orchestrator
from seed_tool_groups      import seed as seed_tool_groups
from seed_sub_agents       import seed as seed_sub_agents
from seed_human_approval   import seed as seed_human_approval
from seed_wait            import seed as seed_wait
from seed_variables       import seed as seed_variables
from seed_field_mapping   import seed as seed_field_mapping
from seed_parallel_fan    import seed as seed_parallel_fan
from seed_mcp_tool        import seed as seed_mcp_tool
from seed_mcp_human_gate  import seed as seed_mcp_human_gate

if __name__ == "__main__":
    print("=== 1. Condition Router ===")
    seed_condition()

    print("\n=== 2. Data Transform Pipeline ===")
    seed_pipeline()

    print("\n=== 3. Remote Agent Chain ===")
    seed_remote()

    print("\n=== 4. Multi-Tool Orchestrator ===")
    seed_orchestrator()

    print("\n=== 5. Tool Groups ===")
    seed_tool_groups()

    print("\n=== 6. Sub Agents ===")
    seed_sub_agents()

    print("\n=== 7. Human Approval ===")
    seed_human_approval()

    print("\n=== 8. Wait ===")
    seed_wait()

    print("\n=== 9. Variables ===")
    seed_variables()

    print("\n=== 10. Field Mapping ===")
    seed_field_mapping()

    print("\n=== 11. Parallel Fan-out ===")
    seed_parallel_fan()

    print("\n=== 12. MCP Tool Call ===")
    seed_mcp_tool()

    print("\n=== 13. MCP Tool Behind a Human Gate ===")
    seed_mcp_human_gate()

    print("\n✓ All workflows seeded.")
