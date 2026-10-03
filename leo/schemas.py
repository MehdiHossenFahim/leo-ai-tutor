"""Structured outputs passed between agents (the 'handoff contracts')."""
from typing import List, Literal
from pydantic import BaseModel, Field


class CoordinatorPlan(BaseModel):
    is_clear: bool = Field(description="False if the request is too vague to teach")
    topic: str = ""
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    clarifying_question: str = ""
    teaching_plan: List[str] = []


class Question(BaseModel):
    id: int
    type: Literal["mcq", "short_answer"]
    question: str
    options: List[str] = []          # only for mcq
    correct_answer: str
    concept: str                      # which concept this tests (used by feedback loop)


class QuizSet(BaseModel):
    topic: str
    questions: List[Question]


class Verdict(BaseModel):
    question_id: int
    correct: bool
    feedback: str
    concept: str


class Evaluation(BaseModel):
    verdicts: List[Verdict]
    weak_concepts: List[str] = []
    summary: str = ""

    @property
    def score(self) -> float:
        """Computed in code, not trusted from the LLM."""
        if not self.verdicts:
            return 0.0
        return sum(v.correct for v in self.verdicts) / len(self.verdicts)
