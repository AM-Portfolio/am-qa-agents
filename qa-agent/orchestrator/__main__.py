"""Run as: python -m orchestrator"""

from composition.env_bootstrap import load_env

load_env()

from orchestrator.worker_main import main

if __name__ == "__main__":
    main()
