# Terminal-Bench Integration with AgentBeats Platform

## Executive Summary

This proposal outlines a systematic approach to integrate **terminal-bench** (a benchmark for testing AI agents in terminal environments) into the **agentbeats** platform (a standardized agent evaluation and battle orchestration system) as a "green agent" evaluation scenario. This integration will enable reproducible, standardized evaluation of coding agents on terminal-based tasks through the A2A protocol.

---

## 1. System Analysis

### 1.1 Terminal-Bench Architecture

**Core Components:**
- **Dataset**: ~100 terminal-based tasks covering coding, debugging, systems administration, ML training, etc.
- **Execution Harness**: Sandboxed Docker environments with task-specific configurations
- **Agent Interface**: Supports multiple agent types (Terminus, OpenHands, Claude Code, Aider, etc.)
- **Evaluation**: Automated test scripts with pytest-based parsing
- **Task Structure**:
  - `task.yaml`: Metadata, instruction, timeouts, categories
  - `docker-compose.yml`: Environment configuration
  - `run-tests.sh`: Test execution script
  - Reference solutions

**Key Files:**
- `terminal_bench/harness/harness.py`: Main execution orchestrator
- `terminal_bench/agents/base_agent.py`: Agent interface definition
- `terminal_bench/dataset/dataset.py`: Dataset management

### 1.2 AgentBeats Architecture

**Core Components:**
- **AgentBeats SDK**: Python library for creating A2A-compatible agents
- **Agent Cards**: TOML-based agent configuration
- **Battle Workflow**: Green agent orchestrates white agent evaluation
- **A2A Protocol**: JSON-RPC 2.0 over HTTP for agent communication
- **Recording & Evaluation**: Automatic trajectory capture and scoring

**Key Components:**
- Green Agent: Orchestrator/evaluator (benchmark host)
- White Agent: Agent being tested
- Backend: Battle management and result persistence
- Frontend: Visualization and leaderboards

---

## 2. Integration Requirements Analysis

### 2.1 Task Definition (Guide Step 1)
**Task**: Evaluate coding agents' ability to complete terminal-based programming tasks

### 2.2 Environment Design (Guide Step 2)

**Tools & Actions:**
- **Terminal Access**: Agents interact with sandboxed Docker containers via tmux sessions
- **File Operations**: Read, write, edit files within the container
- **Command Execution**: Run arbitrary shell commands (bash, python, npm, etc.)
- **Environment Feedback**: Command output, file contents, test results

**Interface Considerations:**
- Terminal-bench uses direct tmux session access
- AgentBeats uses A2A message passing
- **Bridge Needed**: Convert A2A messages ↔ terminal commands

### 2.3 Evaluation Metrics (Guide Step 3)

**Primary Metrics:**
- **Success Rate**: Percentage of tasks where all tests pass
- **Pass@k**: Probability of success in k attempts
- **Token Usage**: Input/output tokens consumed
- **Time**: Agent execution time

**Secondary Metrics:**
- **Failure Modes**: Categorized errors (timeout, parse error, test failure)
- **Task Categories**: Performance by difficulty/category

### 2.4 Test Case Design (Guide Step 4)

**Scenarios to Cover:**
- ✅ Agent successfully completes task
- ❌ Agent times out (exceeds max_agent_timeout_sec)
- ❌ Agent produces incorrect solution (tests fail)
- ❌ Agent fails to parse/understand instruction
- ❌ Agent encounters environment issues (missing dependencies)
- ❌ Agent uses excessive resources

---

## 3. Integration Design

### 3.1 Component Mapping

```
Terminal-Bench → AgentBeats Mapping:

1. Terminal-Bench Harness → Green Agent (Evaluator)
2. Terminal-Bench BaseAgent → White Agent (Under Test)
3. Task Dataset → Battle Scenarios
4. Test Scripts → Green Agent Evaluation Tools
5. Docker Containers → Arena Environment Resources
```

### 3.2 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentBeats Backend                        │
│  - Battle Registration & Management                          │
│  - Agent Registry & Launcher Control                         │
│  - Results Storage & Leaderboard                             │
└────────────────┬────────────────────────────────────────────┘
                 │ A2A Protocol
                 │ (JSON-RPC 2.0 / HTTP)
                 │
    ┌────────────┴─────────────┐
    │                          │
    ▼                          ▼
┌─────────────────┐    ┌─────────────────┐
│  Green Agent    │    │  White Agent    │
│  (Evaluator)    │◄───┤  (Under Test)   │
│                 │A2A │                 │
│ - Task Manager  │    │ - Task Solver   │
│ - Env Setup     │    │ - Command Gen   │
│ - Test Runner   │    │ - Code Writing  │
│ - Scorer        │    │                 │
└────────┬────────┘    └─────────────────┘
         │
         │ Direct Access
         │
         ▼
┌─────────────────────────────────────────┐
│      Docker Container Arena             │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  Task Environment                │  │
│  │  - File System                   │  │
│  │  - Languages & Tools             │  │
│  │  - Test Scripts                  │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 3.3 Workflow Sequence

```
1. Battle Initiation
   Backend → Green Agent: "Start battle for task X with white agent Y"

2. Environment Preparation (Green Agent)
   - Pull task from terminal-bench dataset
   - Spin up Docker container
   - Initialize tmux session
   - Set up logging/recording

3. Task Assignment (Green Agent → White Agent via A2A)
   - Send task instruction
   - Provide environment context
   - Share available actions

4. Task Execution (White Agent)
   - Request terminal access via A2A tools
   - Execute commands through green agent proxy
   - Submit solution

5. Evaluation (Green Agent)
   - Run test scripts
   - Parse results
   - Calculate metrics
   - Report to backend

6. Results Recording
   - Store trajectories
   - Update leaderboard
   - Archive artifacts
```

---

## 4. Implementation Plan

### 4.1 Green Agent Implementation

**Location**: `terminal-bench-green-agent/` (this repository)

**Core Components:**

#### 4.1.1 Agent Card (`green_agent_card.toml`)
```toml
name                = "Terminal-Bench Green Agent"
description         = '''
You are the green agent orchestrating terminal-bench evaluations.

## Your Role
- Load tasks from terminal-bench dataset
- Spin up Docker environments
- Send task instructions to white agents via A2A
- Monitor white agent actions through tool usage
- Run evaluation scripts
- Report results

## Available Tools
You have access to these tools for white agents:
- execute_command: Run commands in the Docker environment
- read_file: Read file contents
- write_file: Write file contents
- submit_solution: Trigger evaluation

## Workflow
1. Receive battle configuration with task_id and white_agent_url
2. Setup Docker environment for the task
3. Send task instruction to white agent
4. Provide tools for white agent to interact with environment
5. Run tests when white agent submits
6. Report results to backend
'''
url                 = "http://localhost:9999/"
version             = "1.0.0"

defaultInputModes   = ["text"]
defaultOutputModes  = ["text"]

[capabilities]
streaming           = true  # Required for A2A protocol

[[skills]]
id          = "evaluate_coding_task"
name        = "Evaluate Coding Task"
description = "Evaluate an agent's ability to complete terminal-based programming tasks from the terminal-bench dataset"
tags        = ["evaluation", "coding", "terminal"]
examples    = ["Evaluate agent on task hello-world", "Run terminal-bench evaluation for task csv-to-parquet"]
```

#### 4.1.2 Evaluation Tools (`tools.py`)

**Tool 1: `execute_command`**
```python
@ab_agent.tool
def execute_command(command: str) -> dict:
    """
    Execute a command in the task's Docker environment.
    Used by white agent to interact with the terminal.

    Args:
        command: Shell command to execute

    Returns:
        Dict with terminal_command, terminal_output, and success keys
    """
    if not battle_state.current_session:
        return {
            "success": False,
            "error": "No active session. Call start_battle first.",
            "terminal_command": command,
            "terminal_output": ""
        }

    try:
        # Send command with blocking wait
        battle_state.current_session.send_keys(
            keys=[command, "Enter"],
            block=True,
            max_timeout_sec=30.0
        )
        # Capture the output
        output = battle_state.current_session.capture_pane(capture_entire=False)

        return {
            "success": True,
            "terminal_command": command,
            "terminal_output": output,
            "asciinema_url": None  # Optional: add recording URL later
        }
    except TimeoutError:
        return {
            "success": False,
            "error": "Command timed out after 30 seconds",
            "terminal_command": command,
            "terminal_output": ""
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error executing command: {str(e)}",
            "terminal_command": command,
            "terminal_output": ""
        }
```

**Tool 2: `read_file`**
```python
@ab_agent.tool
def read_file(path: str) -> str:
    """
    Read file contents from the task environment.

    Args:
        path: File path relative to /app

    Returns:
        File contents or error message
    """
    if not battle_state.current_session:
        return "Error: No active session."

    try:
        # Use cat to read file contents
        battle_state.current_session.send_keys(
            keys=[f"cat {path}", "Enter"],
            block=True,
            max_timeout_sec=10.0
        )
        output = battle_state.current_session.capture_pane(capture_entire=False)
        return output
    except Exception as e:
        return f"Error reading file: {str(e)}"
```

**Tool 3: `write_file`**
```python
@ab_agent.tool
def write_file(path: str, content: str) -> str:
    """
    Write content to a file in the task environment.

    Args:
        path: File path relative to /app
        content: Content to write

    Returns:
        Success message or error
    """
    if not battle_state.current_session:
        return "Error: No active session."

    try:
        # Use heredoc to avoid shell escaping issues
        cmd = f"cat > {path} << 'EOF'\n{content}\nEOF"
        battle_state.current_session.send_keys(
            keys=[cmd, "Enter"],
            block=True,
            max_timeout_sec=10.0
        )
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"
```

**Tool 4: `submit_solution`**
```python
@ab_agent.tool
def submit_solution() -> str:
    """
    Trigger evaluation of the white agent's solution.
    Runs the test suite and reports results to the backend.
    """
    from agentbeats.logging import update_battle_process, get_battle_id, get_backend_url

    if not battle_state.current_terminal or not battle_state.current_trial:
        return "Error: No active battle. Call start_battle first."

    try:
        update_battle_process(
            battle_id=get_battle_id(),
            backend_url=get_backend_url(),
            message="Running evaluation tests",
            detail={"task_id": battle_state.current_trial.task_id},
            reported_by="Terminal-Bench Green Agent"
        )

        # Run evaluation with task parameter for parser selection
        result = _run_evaluation(
            terminal=battle_state.current_terminal,
            session=battle_state.current_session,
            task_paths=battle_state.current_trial.task_paths,
            task=battle_state.current_trial.task,
            max_test_timeout_sec=battle_state.current_trial.task.max_test_timeout_sec
        )

        # Report detailed results to backend
        update_battle_process(
            battle_id=get_battle_id(),
            backend_url=get_backend_url(),
            message=f"Evaluation complete. Success: {result['is_resolved']}",
            detail=result,
            reported_by="Terminal-Bench Green Agent"
        )

        # Report final battle result
        from agentbeats.logging import get_battle_id, get_backend_url
        # Note: report_on_battle_end should be called via MCP tool if available
        # For now, we log the completion

        success_msg = f"Evaluation complete.\n"
        success_msg += f"- Tests Passed: {result.get('num_passed', 0)}/{result.get('num_tests', 0)}\n"
        success_msg += f"- Success: {result['is_resolved']}\n"
        success_msg += f"- Failure Mode: {result.get('failure_mode', 'UNKNOWN')}"

        return success_msg

    except Exception as e:
        error_msg = f"Error during evaluation: {str(e)}"
        update_battle_process(
            battle_id=get_battle_id(),
            backend_url=get_backend_url(),
            message=error_msg,
            detail={"error": str(e)},
            reported_by="Terminal-Bench Green Agent"
        )
        return error_msg
```

#### 4.1.3 Main Orchestrator (`main.py`)

```python
# Standard library imports
import atexit
from pathlib import Path
from typing import Optional

# Third-party imports
import agentbeats as ab

# Terminal-bench imports
from terminal_bench.dataset import Dataset
from terminal_bench.terminal.terminal import spin_up_terminal
from terminal_bench.handlers.trial_handler import TrialHandler
from terminal_bench.parsers.parser_factory import ParserFactory
from terminal_bench.parsers.base_parser import UnitTestStatus

# AgentBeats imports
from agentbeats.logging import (
    update_battle_process,
    get_battle_id,
    get_backend_url,
    get_agent_id,
    get_frontend_agent_name
)
from agentbeats.utils.agents.a2a import send_message_to_agent

# Initialize BeatsAgent with explicit configuration
ab_agent = ab.BeatsAgent(
    name="Terminal-Bench Green Agent",
    agent_host="0.0.0.0",
    agent_port=9999,
    model_type="openai",  # or "openrouter"
    model_name="o4-mini"  # or your preferred model
)

# Global state (managed per battle)
class BattleState:
    def __init__(self):
        self.dataset = Dataset(name="terminal-bench-core", version="0.1.1")
        self.current_terminal: Optional[object] = None
        self.current_session: Optional[object] = None
        self.current_trial: Optional[TrialHandler] = None
        self.white_agent_url: Optional[str] = None

battle_state = BattleState()

def _run_evaluation(
    terminal,
    session,
    task_paths,
    task,
    max_test_timeout_sec: float
) -> dict:
    """Execute test scripts and parse results."""
    from terminal_bench.parsers.parser_factory import ParserFactory
    from terminal_bench.parsers.base_parser import UnitTestStatus

    # 1. Copy test files to container
    terminal.copy_to_container(
        paths=[task_paths.run_tests_path, task_paths.test_dir],
        container_dir="/workspace/tests/"
    )

    # 2. Execute test script
    try:
        session.send_keys(
            keys=["bash /workspace/tests/run-tests.sh", "Enter"],
            block=True,
            max_timeout_sec=max_test_timeout_sec
        )
        test_passed = True
    except TimeoutError:
        return {"failure_mode": "TEST_TIMEOUT", "is_resolved": False}

    # 3. Capture output
    post_test_output = session.capture_pane(capture_entire=True)

    # 4. Parse with appropriate parser based on task configuration
    parser = ParserFactory.get_parser(task.parser_name)

    try:
        results = parser.parse(post_test_output)
        # results is dict[str, UnitTestStatus]
        # UnitTestStatus enum: PASSED, FAILED

        is_resolved = all(
            status == UnitTestStatus.PASSED
            for status in results.values()
        )

        return {
            "is_resolved": is_resolved,
            "test_results": {k: v.value for k, v in results.items()},  # Convert enum to string
            "failure_mode": "NONE" if is_resolved else "TEST_FAILED",
            "num_tests": len(results),
            "num_passed": sum(1 for s in results.values() if s == UnitTestStatus.PASSED)
        }
    except Exception as e:
        return {
            "failure_mode": "PARSE_ERROR",
            "is_resolved": False,
            "error": str(e)
        }

# Battle initialization tool
@ab_agent.tool
async def start_battle(task_id: str, white_agent_url: str) -> str:
    """
    Initialize a new terminal-bench battle for the given task.

    Args:
        task_id: The ID of the task to run (e.g., "hello-world")
        white_agent_url: The A2A URL of the white agent to test

    Returns:
        Success message with battle details
    """
    from agentbeats.logging import update_battle_process, get_battle_id, get_backend_url
    from agentbeats.utils.agents.a2a import send_message_to_agent

    try:
        # Update battle progress
        update_battle_process(
            battle_id=get_battle_id(),
            backend_url=get_backend_url(),
            message=f"Initializing battle for task: {task_id}",
            detail={"task_id": task_id, "white_agent_url": white_agent_url},
            reported_by="Terminal-Bench Green Agent"
        )

        battle_state.white_agent_url = white_agent_url

        # Get task from dataset
        task_path = None
        for t in battle_state.dataset:
            if t.name == task_id:
                task_path = t
                break

        if not task_path:
            return f"Error: Task {task_id} not found in dataset"

        # Setup trial handler
        battle_state.current_trial = TrialHandler(
            trial_name=f"{task_id}.1-of-1.battle",
            input_path=task_path,
            output_path=Path("/tmp/terminal-bench-battles")
        )

        # Update progress
        update_battle_process(
            battle_id=get_battle_id(),
            backend_url=get_backend_url(),
            message="Starting Docker environment",
            detail={"docker_image": battle_state.current_trial.client_image_name},
            reported_by="Terminal-Bench Green Agent"
        )

        # Spin up Docker
        battle_state.current_terminal = spin_up_terminal(
            client_container_name=battle_state.current_trial.client_container_name,
            client_image_name=battle_state.current_trial.client_image_name,
            docker_compose_path=battle_state.current_trial.task_paths.docker_compose_path,
            docker_image_name_prefix=battle_state.current_trial.docker_image_name_prefix,
            sessions_logs_path=battle_state.current_trial.trial_paths.sessions_path,
            no_rebuild=False,
            cleanup=True
        ).__enter__()  # Note: Need to manage context properly

        battle_state.current_session = battle_state.current_terminal.create_session(
            "agent",
            as_configured_user=True
        )

        # Send task to white agent
        instruction = battle_state.current_trial.instruction

        update_battle_process(
            battle_id=get_battle_id(),
            backend_url=get_backend_url(),
            message="Sending task instruction to white agent",
            detail={"instruction": instruction},
            reported_by="Terminal-Bench Green Agent"
        )

        await send_message_to_agent(
            target_url=white_agent_url,
            message=f"""
Task: {instruction}

You have access to the following tools to complete this task:
- execute_command(command): Run shell commands
- read_file(path): Read file contents
- write_file(path, content): Write to files
- submit_solution(): Submit when done

Please use these tools to complete the task, then call submit_solution().
"""
        )

        return f"Battle started successfully for task: {task_id}. White agent has been sent the instruction."

    except Exception as e:
        error_msg = f"Error starting battle: {str(e)}"
        update_battle_process(
            battle_id=get_battle_id(),
            backend_url=get_backend_url(),
            message=error_msg,
            detail={"error": str(e)},
            reported_by="Terminal-Bench Green Agent"
        )
        return error_msg

# Docker cleanup
import atexit

def cleanup_battle():
    """Clean up Docker resources."""
    if battle_state.current_terminal:
        try:
            battle_state.current_terminal.__exit__(None, None, None)
        except:
            pass

    battle_state.current_terminal = None
    battle_state.current_session = None

# Register cleanup
atexit.register(cleanup_battle)

# Also cleanup after each battle
@ab_agent.tool
def end_battle() -> str:
    """End current battle and cleanup resources."""
    cleanup_battle()
    return "Battle ended, resources cleaned up"

if __name__ == "__main__":
    ab_agent.load_agent_card("green_agent_card.toml")
    ab_agent.run()
```

### 4.2 White Agent Adapter

**Challenge**: Terminal-bench agents expect direct tmux access, but need A2A interface.

**Solution**: Create adapter wrapper

**Location**: `terminal-bench-green-agent/white_agent_adapter/` (this repository)

```python
# adapter.py
from terminal_bench.agents.base_agent import BaseAgent
from agentbeats.utils.agents.a2a import create_a2a_client, send_message_to_agent
import asyncio

class A2AWhiteAgentAdapter(BaseAgent):
    """
    Adapter that wraps A2A-compatible white agents to work with
    terminal-bench's BaseAgent interface.
    """

    def __init__(self, agent_url: str, **kwargs):
        super().__init__(**kwargs)
        self.agent_url = agent_url

    def perform_task(self, instruction: str, session: TmuxSession,
                     logging_dir: Path) -> AgentResult:
        """
        Translate terminal-bench interface → A2A messages
        """
        # Send initial instruction via A2A
        response = asyncio.run(send_message_to_agent(self.agent_url, instruction))

        # Process tool calls from white agent
        # Execute commands in tmux session
        # Return agent result with token counts
```

### 4.3 Kickoff Script

**Location**: `terminal-bench-green-agent/kickoff.py` (this repository)

```python
import asyncio
import json
from uuid import uuid4
from agentbeats.utils.agents.a2a import send_message_to_agent

async def main():
    green_agent_url = "http://localhost:9999"
    white_agent_url = "http://localhost:8001"
    backend_url = "http://localhost:8000"  # AgentBeats backend

    # Generate battle ID
    battle_id = str(uuid4())

    # Step 1: Initialize battle context with green agent
    battle_init_message = json.dumps({
        "agent_name": "Terminal-Bench Green Agent",
        "agent_id": "green-terminal-bench",
        "battle_id": battle_id,
        "backend_url": backend_url
    })

    print(f"Initializing battle {battle_id}...")
    init_response = await send_message_to_agent(
        target_url=green_agent_url,
        message=battle_init_message
    )
    print(f"Battle initialized: {init_response}")

    # Step 2: Start the battle with task configuration
    task_config = {
        "task_id": "hello-world",
        "white_agent_url": white_agent_url,
    }

    start_message = f"""
    Start terminal-bench battle for task: {task_config['task_id']}.

    Configuration:
    - Task ID: {task_config['task_id']}
    - White Agent URL: {white_agent_url}

    Please call the start_battle tool to initialize the Docker environment and begin evaluation.
    """

    print(f"Starting battle for task {task_config['task_id']}...")
    response = await send_message_to_agent(
        target_url=green_agent_url,
        message=start_message
    )
    print("Battle Results:", response)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 5. Key Design Decisions

### 5.1 Interface Choice: A2A + Tool-Based Access

**Rationale**: Terminal-bench requires direct terminal access, which doesn't naturally fit A2A's message-passing model.

**Solution**:
- Green agent maintains tmux session
- White agent requests actions via A2A tool calls
- Green agent executes in environment and returns results

**Advantages**:
- Maintains A2A standardization
- Isolates white agent from environment details
- Enables trajectory recording
- Supports any A2A-compatible agent

### 5.2 Evaluation Responsibility

**Decision**: Green agent runs evaluation internally

**Rationale**:
- Terminal-bench test scripts are designed for local execution
- Green agent has direct Docker access
- Avoids exposing test infrastructure to white agent
- Matches terminal-bench architecture

### 5.3 Task Selection

**Start Small**:
- Phase 1: Single task (`hello-world`)
- Phase 2: Task subset (10-20 easy tasks)
- Phase 3: Full dataset (~100 tasks)

**Configuration**:
```python
# In kickoff script
task_ids = ["hello-world", "fibonacci-server", "csv-to-parquet"]
# OR
dataset_config = {"name": "terminal-bench-core", "n_tasks": 10}
```

---

## 6. Integration with AgentBeats Platform

### 6.1 Backend Integration

**Register Green Agent**:
```python
# Green agent provides agent card at /.well-known/agent.json
# Backend discovers via A2A protocol
```

**Battle Registration**:
```json
{
  "scenario": "terminal-bench",
  "green_agent_id": "tb-green-agent-1",
  "white_agents": [
    {"id": "agent-under-test-1", "role": "solver"}
  ],
  "config": {
    "task_id": "hello-world",
    "dataset": "terminal-bench-core:0.1.1"
  }
}
```

### 6.2 Result Reporting

**Green Agent → Backend**:
```python
@ab.tool
def report_results(results: dict) -> str:
    """Report battle results to backend"""
    # Use MCPCP battle recording tool
    ab.record_battle_result({
        "task_id": results["task_id"],
        "white_agent_id": results["white_agent_id"],
        "success": results["is_resolved"],
        "metrics": {
            "pass_rate": results["pass_rate"],
            "total_tokens": results["total_tokens"],
            "execution_time_sec": results["execution_time"],
        },
        "failure_mode": results.get("failure_mode"),
        "artifacts": results.get("artifacts", [])
    })
```

### 6.3 Trajectory Recording

**Automatic Recording**:
- A2A message history (green ↔ white)
- Tool call traces
- Terminal session logs (asciinema)
- Test outputs

**Storage**:
```
results/
├── battle_{id}/
│   ├── trajectory.json      # A2A messages
│   ├── tool_calls.json       # Tool usage
│   ├── terminal.cast         # asciinema recording
│   ├── test_output.txt       # Test results
│   └── metrics.json          # Computed metrics
```

---

## 7. Testing & Validation Strategy

### 7.1 Unit Tests

```python
# tests/test_green_agent_tools.py
def test_execute_command():
    """Test command execution in Docker"""
    result = execute_command("echo 'hello'")
    assert result == "hello\n"

def test_file_operations():
    """Test read/write file tools"""
    write_file("/app/test.txt", "content")
    assert read_file("/app/test.txt") == "content"
```

### 7.2 Integration Tests

**Test Cases** (per Guide Step 4):

1. **Success Case**: White agent completes task correctly
   - Task: `hello-world`
   - Expected: `is_resolved=True`, all tests pass

2. **Timeout Case**: White agent exceeds time limit
   - Task: Complex task with short timeout
   - Expected: `failure_mode=AGENT_TIMEOUT`

3. **Wrong Solution**: White agent completes but tests fail
   - Task: `fibonacci-server` with incorrect logic
   - Expected: `is_resolved=False`, specific test failures

4. **Parse Error**: White agent produces malformed output
   - Expected: `failure_mode=PARSE_ERROR`

5. **Environment Issue**: Missing dependencies
   - Expected: Clear error message, guidance

### 7.3 Validation Metrics

**Green Agent Quality** (per Grading Rubric):

- ✅ **Evaluator Quality**: Clear, consistent scoring
- ✅ **Validation**: Manual spot-checks on 10-20 runs
- ✅ **Reliability**: Runs robustly on AgentBeats infrastructure
- ✅ **Realism**: Real-world programming tasks from terminal-bench
- ✅ **Impact**: Well-documented, reproducible, extensible

---

## 8. Challenges & Mitigations

| Challenge | Impact | Mitigation |
|-----------|--------|------------|
| **Terminal access via A2A** | High - Core functionality | Tool-based proxy pattern |
| **Docker resource limits** | Medium - Scalability | Container resource quotas, cleanup |
| **Long-running tasks** | Medium - UX | Timeout configuration, streaming updates |
| **Test script diversity** | Low - Maintenance | Standardize on pytest parser |
| **Agent compatibility** | Medium - Adoption | Provide adapter template, docs |

---

## 9. Phased Rollout Plan

### Phase 1: Proof of Concept (Week 1-2)
- ✅ Implement green agent with 1 simple task (`hello-world`)
- ✅ Create white agent adapter
- ✅ Manual testing of full workflow
- **Success Criteria**: Single battle completes end-to-end

### Phase 2: Core Scenarios (Week 3-4)
- ✅ Expand to 10-20 diverse tasks
- ✅ Implement all evaluation tools
- ✅ Add trajectory recording
- ✅ Integration tests for edge cases
- **Success Criteria**: 90%+ reliability on 20 tasks

### Phase 3: Platform Integration (Week 5-6)
- ✅ Backend battle registration
- ✅ Frontend visualization
- ✅ Leaderboard integration
- ✅ Public documentation
- **Success Criteria**: External researchers can deploy

### Phase 4: Full Dataset (Week 7-8)
- ✅ Scale to all ~100 tasks
- ✅ Performance optimization
- ✅ Advanced metrics (category breakdowns, etc.)
- ✅ Community feedback incorporation
- **Success Criteria**: NeurIPS 2025 submission ready

---

## 10. Documentation Requirements

### 10.1 User-Facing Docs

**For White Agent Developers**:
```markdown
# Using Terminal-Bench on AgentBeats

## Registering Your Agent
1. Implement A2A protocol interface
2. Support required tools: execute_command, read_file, write_file, submit_solution
3. Register at agentbeats.org/register

## Battle Workflow
1. Receive task instruction via A2A message
2. Use tools to interact with environment
3. Call submit_solution() when done
4. View results on leaderboard
```

**For Green Agent Operators**:
```markdown
# Deploying Terminal-Bench Green Agent

## Prerequisites
- Docker
- Python 3.11+
- AgentBeats SDK

## Setup
```bash
cd terminal-bench-green-agent
pip install -r requirements.txt
python main.py --host 0.0.0.0 --port 9999
```

## Configuration
Edit `config.yaml` to:
- Select tasks/dataset
- Set timeouts
- Configure resources
```

### 10.2 Technical Docs

- API Reference (green agent tools)
- Architecture diagrams
- Troubleshooting guide
- Performance benchmarks

---

## 11. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Reliability** | >95% battles complete | Failed/total battles |
| **Evaluator Accuracy** | >90% agreement with manual eval | Human validation on 50 samples |
| **Agent Adoption** | 10+ white agents registered | Platform analytics |
| **Task Coverage** | 90+ tasks supported | Dataset size |
| **Performance** | <2hr per 100 tasks | Battle duration tracking |
| **User Satisfaction** | 4+/5 rating | Post-battle surveys |

---

## 12. Conclusion

This proposal provides a comprehensive, systematic approach to integrating terminal-bench into agentbeats as a green agent evaluation scenario. The design:

✅ **Follows the Green Agent Guide**: Addresses all 4 checklist steps (task, environment, metrics, test cases)

✅ **Leverages Existing Infrastructure**: Reuses terminal-bench's robust task dataset and agentbeats' battle orchestration

✅ **Maintains Standards**: Uses A2A protocol for interoperability

✅ **Is Production-Ready**: Includes testing, validation, documentation, and phased rollout

✅ **Scales**: Supports single tasks → full dataset, manual testing → automated leaderboard

✅ **Meets NeurIPS Criteria**: Novel, large-scale, well-validated, realistic, reproducible

**Next Steps**: Approve proposal → Begin Phase 1 implementation → Iterate based on testing results

---

**Estimated Timeline**: 8 weeks to full deployment

**Resource Requirements**: 1-2 engineers, compute for Docker environments

**Risk Level**: Low-Medium (proven components, clear architecture)
