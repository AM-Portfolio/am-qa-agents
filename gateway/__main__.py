"""Run as: python -m gateway"""

from composition.env_bootstrap import load_env

load_env()

from gateway.app import main

if __name__ == "__main__":
    main()
