import re
import subprocess
import sys
import tempfile
from pathlib import Path

from langfuse import observe

from ..llm import get_llm_lite
from ..state import AgentState
from ..tracing import get_langfuse, traced_llm, tracing_enabled

TIMEOUT_SECONDS = 10
MAX_OUTPUT_CHARS = 2000


def _extract_code(text: str) -> str:
    match = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


@observe(as_type="agent", name="code-agent")
def code_agent(state: AgentState) -> dict:
    prompt = (
        f"Write Python to answer: {state['question']}. "
        "Use only the standard library, no internet/file access. "
        "print() the final result. Code only, no explanation, no markdown fences."
    )
    raw = traced_llm("code-generate", get_llm_lite(temperature=0), prompt).content
    code = _extract_code(raw)

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        script_path = f.name

    try:
        # subprocess + timeout is the sandbox boundary here — the whole backend
        # already runs in its own container, this caps a single runaway script
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        output = proc.stdout.strip() or proc.stderr.strip()
    except subprocess.TimeoutExpired:
        output = f"(execution timed out after {TIMEOUT_SECONDS}s)"
    finally:
        Path(script_path).unlink(missing_ok=True)

    result = output[:MAX_OUTPUT_CHARS]

    if tracing_enabled():
        get_langfuse().update_current_span(
            input=state["question"], output={"code": code, "result": result}
        )

    return {
        "code_result": result,
        "steps": state["steps"] + ["code"],
    }
