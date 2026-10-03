"""Streamlit UI for Leo. Run: streamlit run app.py"""
import streamlit as st
from leo.orchestrator import Leo, LeoError, MAX_ROUNDS

st.set_page_config(page_title="Leo - AI Tutor", page_icon=":material/school:", layout="wide")

# Modern, minimal styling
st.markdown("""
<style>
    /* Clean up the main area */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 800px;
    }
    
    /* Typography tweaks */
    h1, h2, h3 {
        font-weight: 600 !important;
        letter-spacing: -0.02em;
    }
    
    /* Minimal inputs */
    .stTextInput input {
        border-radius: 8px;
    }
    
    /* Subtle button styling */
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        margin-top: 60px;
        padding-top: 20px;
        border-top: 1px solid rgba(128,128,128,0.2);
        color: rgba(128,128,128,0.8);
        font-size: 0.9em;
    }
    .footer a {
        color: #4A90E2;
        text-decoration: none;
    }
    .footer a:hover {
        text-decoration: underline;
    }
</style>
""", unsafe_allow_html=True)

ICON = {"Coordinator": ":material/explore:", "Explainer": ":material/menu_book:", "Quiz Master": ":material/quiz:", "Evaluator": ":material/fact_check:", "Student": ":material/person:"}
ss = st.session_state
for k, v in dict(stage="start", log=[], leo=None, explanation="", quiz=None, ev=None,
                 round=1, plan=None, request="", wrap="").items():
    ss.setdefault(k, v)

# ---------------- sidebar: student, steering (human-in-the-loop), live agent log ----------------
with st.sidebar:
    st.header(":material/psychology: Leo")
    name = st.text_input("Your name", value="Guest")
    level = st.selectbox("Level", ["beginner", "intermediate", "advanced"])
    note = st.text_area("Steer Leo anytime",
                        placeholder="e.g. use more examples / go slower", height=100)
    st.divider()
    st.subheader("Agent activity")
    log_box = st.container()


def render_log():
    with log_box:
        for who, msg in ss.log[-25:]:
            st.markdown(f"{ICON.get(who, ':material/smart_toy:')} **{who}**: {msg}")


def get_leo(status=None) -> Leo:
    def emit(who, msg):
        ss.log.append((who, msg))
        if status:
            status.write(f"{ICON.get(who, ':material/smart_toy:')} **{who}**: {msg}")
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
            st.error(f"{ICON['Coordinator']} Coordinator: {e}")
            return None


st.title("Leo — AI Study Assistant")

# Pure CSS animated placeholder
st.markdown(
    """
    <style>
    /* Hide the real placeholder */
    div[data-testid="stTextInput"] input::placeholder {
        color: transparent !important;
    }
    
    /* Create our animated pseudo-element on the input's direct parent */
    div[data-testid="stTextInput"] div:has(> input) {
        position: relative;
    }
    
    div[data-testid="stTextInput"] div:has(> input)::before {
        content: "e.g. How does recursion work?";
        position: absolute;
        left: 14px;
        top: 50%;
        transform: translateY(-50%);
        color: #888;
        pointer-events: none;
        animation: fadeSwap 12s infinite;
        font-family: inherit;
        font-size: 1rem;
        z-index: 10;
    }
    
    /* Hide when focused or when user has typed (has value) */
    div[data-testid="stTextInput"] div:has(> input:focus)::before,
    div[data-testid="stTextInput"] div:has(> input:not(:placeholder-shown))::before {
        display: none !important;
    }
    
    @keyframes fadeSwap {
        0%   { opacity: 0; content: "e.g. How does recursion work?"; }
        5%   { opacity: 1; content: "e.g. How does recursion work?"; }
        20%  { opacity: 1; content: "e.g. How does recursion work?"; }
        25%  { opacity: 0; content: "e.g. How does recursion work?"; }
        
        26%  { opacity: 0; content: "e.g. Explain quantum mechanics"; }
        30%  { opacity: 1; content: "e.g. Explain quantum mechanics"; }
        45%  { opacity: 1; content: "e.g. Explain quantum mechanics"; }
        50%  { opacity: 0; content: "e.g. Explain quantum mechanics"; }
        
        51%  { opacity: 0; content: "e.g. What caused the fall of Rome?"; }
        55%  { opacity: 1; content: "e.g. What caused the fall of Rome?"; }
        70%  { opacity: 1; content: "e.g. What caused the fall of Rome?"; }
        75%  { opacity: 0; content: "e.g. What caused the fall of Rome?"; }
        
        76%  { opacity: 0; content: "e.g. How do neural networks learn?"; }
        80%  { opacity: 1; content: "e.g. How do neural networks learn?"; }
        95%  { opacity: 1; content: "e.g. How do neural networks learn?"; }
        100% { opacity: 0; content: "e.g. How do neural networks learn?"; }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------- stage machine ----------------
if ss.stage in ("start", "clarify"):
    if ss.stage == "clarify":
        st.info(f"{ICON['Coordinator']} Coordinator needs more detail: **{ss.plan.clarifying_question}**", icon=":material/info:")
    text = st.text_input("What do you want to learn?", placeholder="e.g. How does recursion work?")
    if st.button("Start learning", type="primary", use_container_width=False) and text:
        ss.request = f"{ss.request} {text}".strip() if ss.stage == "clarify" else text
        plan = run("Coordinator planning...", lambda l: l.plan(ss.request))
        if plan:
            ss.plan = plan
            if not plan.is_clear:
                ss.stage = "clarify"
            else:
                res = run("Explainer & Quiz Master...", lambda l: l.teach_and_quiz())
                if res:
                    ss.explanation, ss.quiz = res
                    ss.stage = "quiz"
        st.rerun()

elif ss.stage == "quiz":
    st.subheader(f"Lesson (Round {ss.round})")
    st.markdown(ss.explanation)
    st.divider()
    st.subheader("Quiz")
    with st.form(f"quiz_{ss.round}", border=False):
        answers = {}
        for q in ss.quiz.questions:
            if q.type == "mcq" and q.options:
                answers[q.id] = st.radio(f"**{q.id}. {q.question}**", q.options, index=None, key=f"q{ss.round}_{q.id}")
            else:
                answers[q.id] = st.text_input(f"**{q.id}. {q.question}**", key=f"q{ss.round}_{q.id}")
            st.write("") # slight spacing
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
        icon_res = ":material/check_circle:" if v.correct else ":material/cancel:"
        st.markdown(f"{icon_res} **Q{v.question_id}** ({v.concept}): {v.feedback}")
    st.caption(ev.summary)
    st.divider()
    leo = get_leo()
    if leo.needs_reteach(ev, ss.round):
        st.warning(f"Weak concepts identified: {', '.join(ev.weak_concepts)}. Feedback loop required.", icon=":material/model_training:")
        c1, c2 = st.columns(2)
        if c1.button("Re-teach weak concepts", type="primary", use_container_width=True, icon=":material/refresh:"):
            res = run("Re-teaching and re-testing...",
                      lambda l: l.teach_and_quiz(l.reteach_focus(ev)))
            if res:
                ss.explanation, ss.quiz = res
                ss.round += 1
                ss.stage = "quiz"
                st.rerun()
        if c2.button("Finish session", use_container_width=True, icon=":material/done_all:"):
            ss.wrap = run("Coordinator wrapping up...", lambda l: l.wrap_up(ev)) or ""
            ss.stage = "done"
            st.rerun()
    else:
        ss.wrap = run("Coordinator wrapping up...", lambda l: l.wrap_up(ev)) or ""
        ss.stage = "done"
        st.rerun()

elif ss.stage == "done":
    st.success("Session complete", icon=":material/workspace_premium:")
    st.markdown(ss.wrap)
    if st.button("New topic", type="primary", icon=":material/add:"):
        for k in ("stage", "explanation", "quiz", "ev", "round", "plan", "request", "wrap"):
            del ss[k]
        ss.leo = None
        st.rerun()

render_log()

st.markdown(
    """
    <div class="footer">
        Developed by <a href="https://www.linkedin.com/in/mehedihossenfahim/" target="_blank">Mehedi Hossen Fahim</a>
    </div>
    """,
    unsafe_allow_html=True
)
