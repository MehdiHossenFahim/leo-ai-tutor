from crewai import Agent, Task
from . import prompts as P


def build_agents(llm) -> dict:
    """Each agent: own role, goal, backstory. Delegation is OFF; the Coordinator
    delegates explicitly via the orchestrator so handoffs are deterministic."""
    return {
        key: Agent(llm=llm, allow_delegation=False, verbose=False,
                   max_execution_time=120, max_retry_limit=2, **spec)
        for key, spec in P.AGENTS.items()
    }


def make_task(key: str, agent: Agent, context=None, output=None) -> Task:
    desc, expected = P.TASKS[key]
    kwargs = dict(description=desc, expected_output=expected, agent=agent)
    if context:
        kwargs["context"] = context
    if output:
        kwargs["output_pydantic"] = output
    return Task(**kwargs)
