# Agent skills from Jane Street

A collection of skills for AI agents and chatbots.
Each skill is a directory containing a `SKILL.md` file
with instructions for the agent.

## Skills

- **socratic-tutor** — turns an LLM into a strict personal tutor that teaches a
  topic of your choice using the Socratic method: a diagnostic, a skill map with
  levels 0-5, one question at a time, spaced review, and a final assessment.

## How to use

With a coding agent that supports the common `SKILL.md` format, copy the skill
directory into your agent's skills folder, then ask the agent to use it
("teach me X").

With a plain chatbot, paste the body of the skill's `SKILL.md` into the chat
(or into a custom/system prompt), followed by what you want it to do.

## Fork additions

This fork of [Jane Street's agent_skills](https://github.com/janestreet/agent_skills)
keeps the original tutor instructions, strict tone, skill map, and teaching loop.
It adds a short evidence ledger, verification/provisional judgments, and unseen
transfer checks for independent mastery.

Optional [local persistence and FSRS](socratic-tutor/references/STATE.md) use the
retained Python helper from this fork with separately installed
[Py-FSRS](https://github.com/open-spaced-repetition/py-fsrs). Python 3.10+ is needed
only for the helper. Chat-only use needs no dependencies. State is opt in; there
is no network sync or background reminder service. FSRS schedules recall cards,
not practical mastery.

To run the helper tests, including real FSRS integration:

```sh
python -m pip install 'fsrs>=6,<7'
python -m unittest discover -s socratic-tutor/tests -v
```

The scheduler test is skipped if FSRS is absent; progress tracking still works.
