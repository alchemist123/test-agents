"""Run all 4 workflow seed scripts against the running backend."""
import sys
from seed_condition_router import seed as seed_condition
from seed_data_pipeline    import seed as seed_pipeline
from seed_remote_agent     import seed as seed_remote
from seed_orchestrator     import seed as seed_orchestrator

if __name__ == "__main__":
    print("=== 1. Condition Router ===")
    seed_condition()

    print("\n=== 2. Data Transform Pipeline ===")
    seed_pipeline()

    print("\n=== 3. Remote Agent Chain ===")
    seed_remote()

    print("\n=== 4. Multi-Tool Orchestrator ===")
    seed_orchestrator()

    print("\n✓ All workflows seeded.")
