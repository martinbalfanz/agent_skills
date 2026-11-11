# Agent Skills — experimental fork

This fork of [Jane Street's agent_skills](https://github.com/janestreet/agent_skills) keeps the portable `SKILL.md` format and extends `socratic-tutor` with adaptive pacing, verifiable assessment, a real retrieval scheduler, and optional local session continuity.

## Socratic Tutor

**Without dependencies:** copy [`socratic-tutor/SKILL.md`](socratic-tutor/SKILL.md) into a compatible agent, or paste the instructions into a chatbot. Ask "Teach me X", "Quiz me on Y", or "Help me master Z". It does **not** hijack ordinary explanations.

**With optional local persistence (coding agents):** use [`socratic-tutor/references/STATE.md`](socratic-tutor/references/STATE.md) to set up a user-approved local JSON state file and [Py-FSRS](https://github.com/open-spaced-repetition/py-fsrs) (`pip install 'fsrs>=6,<7'`). The helper requires Python 3.10+, file access, and an explicit state path. `SKILL.md` alone still works without it.

What changed:

- **Modes:** guided Socratic practice, open-ended discovery, independent exam, or direct explanation on request; no forced questionnaire or infinite questioning.
- **Mastery:** evidence-based 0–5 progress, calibrated uncertainty, source-backed exercises, independent transfer, and an integrative final exam. Recall review and mastery are separate.
- **Review:** real FSRS card scheduling where the optional helper is installed, due queue and review history, plus a portable state export. Without it, only best-effort conversational review is available.
- **Privacy:** storage is opt in, local, and not committed by the tool; no network sync, account, background scheduler, or claim of cross-device synchronization.

Example:

```sh
python -m pip install 'fsrs>=6,<7'
python socratic-tutor/scripts/tutor_state.py --state "$HOME/.local/share/socratic-tutor/trading.json" init --topic 'Trading setups' --skill 'entries' --skill 'risk'
python socratic-tutor/scripts/tutor_state.py --state "$HOME/.local/share/socratic-tutor/trading.json" status
```

See [state helper guide](socratic-tutor/references/STATE.md) for the full workflow. Run tests with `python -m unittest discover -s socratic-tutor/tests -v` (FSRS-specific tests run when the dependency is installed).

## Related work and credits

- [Jane Street: agent_skills](https://github.com/janestreet/agent_skills) — original mastery-based `socratic-tutor` and its intent guard, skill map, and assessment structure.
- [bevibing/socrates-skill](https://github.com/bevibing/socrates-skill), raised in [upstream issue #2](https://github.com/janestreet/agent_skills/issues/2) — progressive questioning against source material and mirroring the learner's language. This fork **does not** adopt its never-answer rule.
- [SevenTianyu/socratic-discovery-skills](https://github.com/SevenTianyu/socratic-discovery-skills), raised in [upstream issue #6](https://github.com/janestreet/agent_skills/issues/6) — discovery vs. mastery, mountain/path exploration, green/yellow/red pacing and learner-owned reflection. This fork borrows the useful teaching patterns without claiming the skill is derived from that project.
- [Upstream issue #1](https://github.com/janestreet/agent_skills/issues/1) — Montessori-inspired scaffolding: help learners do it themselves, without withholding needed explanations.
- [Open Spaced Repetition: Py-FSRS](https://github.com/open-spaced-repetition/py-fsrs) — separately installed scheduling implementation, not bundled or rewritten here.

These are design influences and comparisons, **not** claims of endorsement or upstream authorship. The adapter stores card state through Py-FSRS's documented serialization API. See the upstream repositories for their respective licenses.