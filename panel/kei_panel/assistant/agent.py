"""The assistant's loop: question -> tool calls -> answer.

    agent = Agent(model, Context(db), instance="library", lang="pt")
    turn = agent.ask("who has 4 overdue books and 144 reais in fines?", reporter)

`model(messages) -> str` is llm.chat bound to the saved provider (or
DemoModel). The model answers with one JSON envelope per round
({"tool": ..., "args": ...} or {"answer": ...}); a reply that is not
JSON is taken as the answer, so a small local model that forgets the
envelope still gets its text through. ask() BLOCKS: it is the thread job
of run_with_loader, and reports each step to the Pac-Man loader.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from . import prompt, tools
from .llm import Messages

MAX_STEPS = 6
HISTORY_TURNS = 6            # past questions + answers kept for follow-ups

STEP_LABELS = {
    "search_catalogue": "Searching the catalogue",
    "find_patrons": "Looking up patrons",
    "get_record": "Opening the record",
    "search_reports": "Searching saved reports",
    "get_syspref": "Reading system preferences",
    "find_page": "Finding the page",
    "run_select": "Running a read-only query",
    "propose_change": "Preparing a change for your review",
}


@dataclass
class Turn:
    question: str
    answer: str = ""
    steps: list[str] = field(default_factory=list)
    proposals: list[tools.Proposal] = field(default_factory=list)


def parse_envelope(text: str) -> dict:
    """The first complete {...} of the text (parse_json_reply in Vision.pm)."""
    start = text.find("{")
    while start >= 0:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                    except ValueError:
                        break
                    if isinstance(obj, dict):
                        return obj
                    break
        start = text.find("{", start + 1)
    return {}


class Agent:
    def __init__(self, model: Callable[[Messages], str], ctx: tools.Context,
                 instance: str = "library", lang: str = "en", max_steps: int = MAX_STEPS):
        self.model = model
        self.ctx = ctx
        self.max_steps = max_steps
        self.system = prompt.build([t.spec() for t in tools.TOOLS.values()], instance, lang, max_steps)
        self.history: Messages = []

    def reset(self) -> None:
        self.history.clear()
        self.ctx.refs.clear()
        self.ctx.proposals.clear()

    def ask(self, question: str, reporter=None, cancelled: Callable[[], bool] = lambda: False) -> Turn:
        turn = Turn(question)
        first_proposal = len(self.ctx.proposals)
        msgs: Messages = [{"role": "system", "content": self.system}, *self.history,
                          {"role": "user", "content": question}]
        for step in range(self.max_steps + 1):
            if cancelled():
                raise InterruptedError("cancelled")
            if reporter:
                reporter.status("Thinking" if step == 0 else "Reading the results")
            raw = self.model(msgs)
            env = parse_envelope(raw)
            name = env.get("tool")
            if not name or step == self.max_steps:
                answer = env.get("answer") if env else None
                if not isinstance(answer, str) or not answer.strip():
                    answer = raw.strip() if not env else "I could not finish this answer. Please rephrase."
                turn.answer = answer.strip()
                break
            args = env.get("args") if isinstance(env.get("args"), dict) else {}
            label = STEP_LABELS.get(str(name), str(name))
            turn.steps.append(label)
            if reporter:
                reporter.status(label)
                reporter.log(f"{name} {json.dumps(args, ensure_ascii=False)[:200]}")
            result = tools.call(self.ctx, str(name), args)
            msgs += [{"role": "assistant", "content": json.dumps(env, ensure_ascii=False)},
                     {"role": "user", "content": f"TOOL RESULT {name}: {result}"}]
        turn.proposals = self.ctx.proposals[first_proposal:]
        # Follow-ups see the question and the answer, not the raw tool rows.
        self.history += [{"role": "user", "content": question},
                         {"role": "assistant", "content": json.dumps({"answer": turn.answer}, ensure_ascii=False)}]
        self.history = self.history[-2 * HISTORY_TURNS:]
        return turn


# ----------------------------------------------------------------------
# Demo: a scripted model, so --demo and the tests run without a provider
# ----------------------------------------------------------------------
class DemoModel:
    """Answers the three example questions of Module 2 the way a real model should."""

    def __call__(self, messages: Messages) -> str:
        last = messages[-1]["content"]
        if last.startswith("TOOL RESULT"):
            return json.dumps({"answer": self._answer(last)})
        q = last.lower()
        if any(w in q for w in ("clown", "palhaço", "palhaco")):
            call = {"tool": "search_catalogue", "args": {"terms": ["It", "A coisa", "Stephen King", "Pennywise"]}}
        elif any(w in q for w in ("waive", "perdo", "zerar", "clear the fine")):
            call = {"tool": "propose_change", "args": {
                "kind": "sql", "summary": "Waive the outstanding fines of patron 101 (Ana Souza).",
                "sql": "UPDATE accountlines SET amountoutstanding = 0 WHERE borrowernumber = 101 "
                       "AND amountoutstanding > 0"}}
        elif any(w in q for w in ("overdue", "atras", "fine", "multa")):
            nums = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", q)]
            args: dict = {"order": "recent_activity", "limit": 1 if re.search(r"\b(last|último|ultimo)\b", q) else 5}
            if nums:
                args |= {"overdues_min": nums[0], "overdues_max": nums[0]}
            if len(nums) > 1:
                args |= {"fines_min": nums[1], "fines_max": nums[1]}
            call = {"tool": "find_patrons", "args": args}
        elif any(w in q for w in ("drop", "truncate", "delete all", "apagar tudo")):
            return json.dumps({"answer": "I can't do that: structural or unfiltered deletions are never "
                                         "allowed, not even as a proposal."})
        elif any(w in q for w in ("index", "índice", "indice")):
            call = {"tool": "propose_change", "args": {
                "kind": "panel_action", "action": "search-repair",
                "summary": "Rebuild the search index with the panel's own routine."}}
        else:
            call = {"tool": "find_page", "args": {"query": last}}
        return json.dumps(call)

    @staticmethod
    def _answer(result: str) -> str:
        name, _, body = result.removeprefix("TOOL RESULT ").partition(": ")
        data = json.loads(body) if body.startswith("{") else {}
        if "error" in data:
            return f"That did not work: {data['error']}"
        if name == "propose_change":
            return "I prepared the change below. Review it and press **Confirm** to run it, or Cancel."
        rows = next((v for v in data.values() if isinstance(v, list) and v and isinstance(v[0], dict)), [])
        if not rows:
            return "I found nothing matching that."
        if name == "find_patrons":
            r = rows[0]
            return (f"{r['link']} (card {r['cardnumber']}) has {r['overdues']} overdue loans and "
                    f"{r['fines']} in fines; last seen {(r.get('lastseen') or '-')[:10]}.\n"
                    "I read \"last\" as the most recent activity.")
        lines = [f"- {r['link']}" for r in rows[:5]]
        return "Here is what I found:\n" + "\n".join(lines)
