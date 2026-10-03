"""Orchestration: Coordinator-led SEQUENTIAL pipeline with a feedback loop.

 request -> [Coordinator: plan] -> [Explainer] -> [Quiz Master] -> (student answers)
         -> [Evaluator] -> weak? -> [Explainer re-teach] -> [Quiz Master] -> ... -> [Coordinator: wrap-up]
"""
import json, os, re
from crewai import Crew, LLM, Process
from dotenv import load_dotenv

from . import memory
from .agents import build_agents, make_task
from .schemas import CoordinatorPlan, QuizSet, Evaluation

load_dotenv()
MAX_RETRIES = 2
PASS_MARK = 0.7
MAX_ROUNDS = 3


class LeoError(Exception):
    """Raised when an agent stalls/fails after retries; the Coordinator explains it."""


def _parse(out, model):
    if getattr(out, "pydantic", None):
        return out.pydantic
    raw = re.sub(r"^```(?:json)?|```$", "", (out.raw or "").strip(), flags=re.M).strip()
    return model.model_validate_json(raw)


class SafeLLM(LLM):
    def call(self, messages, *args, **kwargs):
        for m in messages:
            m.pop("cache_breakpoint", None)
        return super().call(messages, *args, **kwargs)

class Leo:
    def __init__(self, student: str, emit=None, model: str | None = None):
        self.profile = memory.load(student)
        self.student = student or "Guest"
        self.emit = emit or (lambda who, msg: print(f"[{who}] {msg}"))
        self.llm = SafeLLM(model=model or os.getenv("LEO_MODEL", "groq/openai/gpt-oss-120b"), temperature=0.4)
        self.agents = build_agents(self.llm)
        self.note = "none"      # human-in-the-loop steering from the student
        self.state = dict(topic="", level="beginner", plan="", focus="Teach the full topic",
                          explanation="", quiz=None, n_questions=4)

    # ---------- core runner with retry + Coordinator fallback ----------
    def _run(self, label, build, handoffs, **extra):
        inputs = dict(student=self.student, memory=memory.summarize(self.profile), note=self.note,
                      request="", answers="", score="", weak="", **{k: str(v) for k, v in self.state.items()
                      if k not in ("quiz",)}, quiz=self.state["quiz"].model_dump_json() if self.state["quiz"] else "")
        inputs.update({k: str(v) for k, v in extra.items()})
        for attempt in range(MAX_RETRIES + 1):
            try:
                agents, tasks = build()
                count = {"i": 0}

                def cb(out, handoffs=handoffs, count=count):
                    nxt = handoffs[min(count["i"], len(handoffs) - 1)]
                    self.emit(out.agent or "Agent", f"finished -> handing off to {nxt}")
                    count["i"] += 1

                self.emit("Coordinator", f"{label} (attempt {attempt + 1})")
                crew = Crew(agents=agents, tasks=tasks, process=Process.sequential,
                            task_callback=cb, verbose=False)
                return crew.kickoff(inputs=inputs)
            except Exception as e:  # stall, timeout, rate limit, bad JSON...
                self.emit("Coordinator", f"Problem during '{label}': {type(e).__name__}. "
                          + ("Retrying." if attempt < MAX_RETRIES else "Giving up."))
        raise LeoError(f"'{label}' kept failing. Try rephrasing your request or check your API key/model.")

    # ---------- phases ----------
    def plan(self, request: str) -> CoordinatorPlan:
        a = self.agents
        res = self._run("Coordinator is analysing the request",
                        lambda: ([a["coordinator"]], [make_task("plan", a["coordinator"], output=CoordinatorPlan)]),
                        ["Explainer"], request=request, level=self.state["level"])
        plan = _parse(res.tasks_output[0], CoordinatorPlan)
        if plan.is_clear:
            self.state.update(topic=plan.topic, level=plan.level, plan="; ".join(plan.teaching_plan))
        return plan

    def teach_and_quiz(self, focus: str | None = None) -> tuple[str, QuizSet]:
        a = self.agents
        if focus:
            self.state["focus"] = focus

        def build():
            ex = make_task("explain", a["explainer"])
            qz = make_task("quiz", a["quizmaster"], context=[ex], output=QuizSet)   # <- handoff
            return [a["explainer"], a["quizmaster"]], [ex, qz]

        res = self._run("Explainer + Quiz Master working", build, ["Quiz Master", "Student"])
        self.state["explanation"] = res.tasks_output[0].raw
        quiz = _parse(res.tasks_output[1], QuizSet)
        self.state["quiz"] = quiz
        return self.state["explanation"], quiz

    def evaluate(self, answers: dict[int, str]) -> Evaluation:
        a = self.agents
        text = "\n".join(f"Q{i}: {ans or '(no answer)'}" for i, ans in answers.items())
        res = self._run("Evaluator is grading",
                        lambda: ([a["evaluator"]], [make_task("evaluate", a["evaluator"], output=Evaluation)]),
                        ["Coordinator"], answers=text)          # <- Quiz Master's key handed to Evaluator
        return _parse(res.tasks_output[0], Evaluation)

    def needs_reteach(self, ev: Evaluation, round_no: int) -> bool:
        return ev.score < PASS_MARK and ev.weak_concepts and round_no < MAX_ROUNDS

    def reteach_focus(self, ev: Evaluation) -> str:
        return ("RE-TEACH ONLY these weak concepts with a different approach/analogy than before: "
                + ", ".join(ev.weak_concepts))

    def wrap_up(self, ev: Evaluation) -> str:
        a = self.agents
        res = self._run("Coordinator is writing the wrap-up",
                        lambda: ([a["coordinator"]], [make_task("wrapup", a["coordinator"])]),
                        ["Student"], score=f"{ev.score:.0%}", weak=", ".join(ev.weak_concepts) or "none")
        memory.record(self.profile, self.state["topic"], self.state["level"], ev.score, ev.weak_concepts)
        return res.tasks_output[0].raw
