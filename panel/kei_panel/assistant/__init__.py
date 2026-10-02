"""Module 2: the AI assistant of the dashboard.

  prompt.py    system prompt (persona, boundaries, JSON protocol, links)
  llm.py       one chat round trip with Module 1's provider (vision.conf)
  agent.py     question -> tool calls -> answer; DemoModel for --demo
  tools.py     the tools the model may call; Proposal; verified links
  sqlguard.py  read-only and change checks on SQL
  db.py        the SELECT-only MariaDB account (and DemoDB)
  links.py     [[kind:id|label]] -> blue clickable text
  actions.py   running a proposal after Confirm

The widget is widgets/assistant.py; the record card screens/record.py.
"""

from __future__ import annotations

import tempfile
from functools import partial
from pathlib import Path

from .. import aiconf
from . import db as dbmod
from . import llm
from .agent import Agent, DemoModel
from .tools import Context


def conf_file(env) -> Path:
    """vision.conf of Module 1 (a temp copy in demo mode, as AIView does)."""
    if env.demo:
        return Path(tempfile.gettempdir()) / "kei-demo-ai" / "vision.conf"
    return aiconf.conf_path(env.instance)


def provider(env) -> dict[str, str] | None:
    """The saved provider settings, or None when Module 1 was never saved."""
    path = conf_file(env)
    if not path.is_file():
        return None
    c = aiconf.load(path)
    return None if aiconf.endpoint_problem(c) else c


def make_db(env):
    return dbmod.DemoDB() if env.demo else dbmod.MariaDBReadOnly()


def make_agent(env, database=None) -> Agent | None:
    """None when no provider is configured (and not in demo mode)."""
    c = provider(env)
    if env.demo:
        model = DemoModel()
    elif c is None:
        return None
    else:
        model = partial(llm.chat, c)
    return Agent(model, Context(database or make_db(env)), instance=env.instance, lang=env.lang)
