"""Run as: python -m am_qa_agent.orchestrator.worker_main"""

from am_qa_agent.env_bootstrap import load_env

load_env()

from am_qa_agent.orchestrator.worker_main import main

if __name__ == "__main__":
    main()
