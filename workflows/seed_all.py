"""Run all 7 workflow seed scripts against the running backend."""
from seed_condition_router import seed as seed_condition
from seed_data_pipeline    import seed as seed_pipeline
from seed_remote_agent     import seed as seed_remote
from seed_orchestrator     import seed as seed_orchestrator
from seed_tool_groups      import seed as seed_tool_groups
from seed_sub_agents       import seed as seed_sub_agents
from seed_human_approval   import seed as seed_human_approval

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

    print("\n✓ All workflows seeded.")
