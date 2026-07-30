from pathlib import Path

from langchain_community.utilities import SQLDatabase
from langfuse import observe

from ..config import settings
from ..llm import get_llm_lite
from ..state import AgentState
from ..tracing import get_langfuse, traced_llm, tracing_enabled

_db: SQLDatabase | None = None


def get_db() -> SQLDatabase:
    global _db
    if _db is None:
        abs_path = Path(settings.sqlite_path).resolve()
        # open read-only at the SQLite level — defense in depth on top of the
        # SELECT-only guard below, in case the model ever writes a mutating query
        _db = SQLDatabase.from_uri(f"sqlite:///file:{abs_path}?mode=ro&uri=true")
    return _db


@observe(as_type="agent", name="data-agent")
def data_agent(state: AgentState) -> dict:
    db = get_db()
    prompt = (
        f"Schema:\n{db.get_table_info()}\n\n"
        f"Write exactly one SQLite SELECT query (SQL only, no explanation, no markdown "
        f"code fences) that answers this question: {state['question']}"
    )
    raw = traced_llm("data-sql-generate", get_llm_lite(temperature=0), prompt).content.strip()
    sql = raw.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()

    if not sql.lower().startswith("select"):
        if tracing_enabled():
            get_langfuse().update_current_span(
                input=state["question"], output=f"refused — not read-only: {sql}"
            )
        return {
            "sql_result": f"(refused — generated query was not a read-only SELECT): {sql}",
            "steps": state["steps"] + ["data(sql, refused)"],
        }

    result = db.run(sql)

    if tracing_enabled():
        get_langfuse().update_current_span(
            input=state["question"], output={"sql": sql, "result": str(result)}
        )

    return {
        "sql_result": f"{sql}\n-> {result}",
        "steps": state["steps"] + ["data(sql)"],
    }
