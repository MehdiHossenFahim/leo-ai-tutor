"""Streamlit UI for Leo. Run: streamlit run app.py"""
import streamlit as st
from leo.orchestrator import Leo, LeoError, MAX_ROUNDS

st.set_page_config(page_title="Leo - Multi-Agent Tutor", page_icon="🦁", layout="wide")
ICON = {"Coordinator": "🧭", "Explainer": "👩‍🏫", "Quiz Master": "❓", "Evaluator": "✅", "Student": "🎓"}
ss = st.session_state
for k, v in dict(stage="start", log=[], leo=None, explanation="", quiz=None, ev=None,
                 round=1, plan=None, request="", wrap="").items():
    ss.setdefault(k, v)

# ---------------- sidebar: student, steering (human-in-the-loop), live agent log ----------------
with st.sidebar:
    st.header("🦁 Leo")
    name = st.text_input("Your name", value="Guest")
    level = st.selectbox("Level", ["beginner", "intermediate", "advanced"])
    note = st.text_area("Steer Leo anytime (human-in-the-loop)",
                        placeholder="e.g. use more examples / go slower / make quiz harder")
    st.divider()
    st.subheader("Agent activity")
    log_box = st.container()


def render_log():
    with log_box:
        for who, msg in ss.log[-25:]:
            st.markdown(f"{ICON.get(who, '🤖')} **{who}**: {msg}")


def get_leo(status=None) -> Leo:
    def emit(who, msg):
        ss.log.append((who, msg))
        if status:
            status.write(f"{ICON.get(who, '🤖')} **{who}**: {msg}")
    if ss.leo is None or ss.leo.student != name:
        ss.leo = Leo(name)
    ss.leo.emit = emit
    ss.leo.note = note.strip() or "none"
    ss.leo.state["level"] = level
    return ss.leo


def run(label, fn):
    with st.status(label, expanded=True) as status:
        try:
            out = fn(get_leo(status))
            status.update(label="Done", state="complete")
            return out
        except LeoError as e:
            status.update(label="Coordinator intervened", state="error")
            st.error(f"🧭 Coordinator: {e}")
            return None


st.title("Leo — your multi-agent study assistant")

# ---------------- stage machine ----------------
if ss.stage in ("start", "clarify"):
    if ss.stage == "clarify":
        st.info(f"🧭 Coordinator needs more detail: **{ss.plan.clarifying_question}**")
    text = st.text_input("What do you want to learn?", placeholder="e.g. How does recursion work?")
    if st.button("Start learning", type="primary") and text:
        ss.request = f"{ss.request} {text}".strip() if ss.stage == "clarify" else text
        plan = run("Coordinator planning...", lambda l: l.plan(ss.request))
        if plan:
            ss.plan = plan
            if not plan.is_clear:
                ss.stage = "clarify"
            else:
                res = run("Explainer → Quiz Master...", lambda l: l.teach_and_quiz())
                if res:
                    ss.explanation, ss.quiz = res
                    ss.stage = "quiz"
        st.rerun()

elif ss.stage == "quiz":
    st.subheader(f"Lesson (round {ss.round})")
    st.markdown(ss.explanation)
    st.subheader("Quiz")
    with st.form(f"quiz_{ss.round}"):
        answers = {}
        for q in ss.quiz.questions:
            if q.type == "mcq" and q.options:
                answers[q.id] = st.radio(f"{q.id}. {q.question}", q.options, index=None, key=f"q{ss.round}_{q.id}")
            else:
                answers[q.id] = st.text_input(f"{q.id}. {q.question}", key=f"q{ss.round}_{q.id}")
        submitted = st.form_submit_button("Submit answers", type="primary")
    if submitted:
        ev = run("Evaluator grading...", lambda l: l.evaluate({k: v or "" for k, v in answers.items()}))
        if ev:
            ss.ev, ss.stage = ev, "review"
            st.rerun()

elif ss.stage == "review":
    ev = ss.ev
    st.subheader(f"Score: {ev.score:.0%}")
    for v in ev.verdicts:
        st.markdown(f"{'✅' if v.correct else '❌'} **Q{v.question_id}** ({v.concept}): {v.feedback}")
    st.caption(ev.summary)
    leo = get_leo()
    if leo.needs_reteach(ev, ss.round):
        st.warning(f"Weak concepts: {', '.join(ev.weak_concepts)}. Feedback loop: re-teach?")
        c1, c2 = st.columns(2)
        if c1.button("🔁 Re-teach weak concepts", type="primary"):
            res = run("Evaluator → Explainer → Quiz Master (feedback loop)...",
                      lambda l: l.teach_and_quiz(l.reteach_focus(ev)))
            if res:
                ss.explanation, ss.quiz = res
                ss.round += 1
                ss.stage = "quiz"
                st.rerun()
        if c2.button("Finish session"):
            ss.wrap = run("Coordinator wrapping up...", lambda l: l.wrap_up(ev)) or ""
            ss.stage = "done"
            st.rerun()
    else:
        ss.wrap = run("Coordinator wrapping up...", lambda l: l.wrap_up(ev)) or ""
        ss.stage = "done"
        st.rerun()

elif ss.stage == "done":
    st.success("Session complete 🎉")
    st.markdown(ss.wrap)
    if st.button("New topic"):
        for k in ("stage", "explanation", "quiz", "ev", "round", "plan", "request", "wrap"):
            del ss[k]
        ss.leo = None
        st.rerun()

render_log()
