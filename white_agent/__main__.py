"""
Entry point for running the white agent as a module.

By default, uses the LLM-powered agent. Use --simple for the basic agent.
"""

import sys

# Use LLM agent by default
if "--simple" in sys.argv:
    sys.argv.remove("--simple")
    from white_agent.white_agent import main
else:
    from white_agent.llm_white_agent import main

if __name__ == "__main__":
    main()
