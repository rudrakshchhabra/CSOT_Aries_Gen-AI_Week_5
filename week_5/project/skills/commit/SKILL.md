---
name: commit
description: Stage verified code changes and generate a clean conventional-commit message. Use when the user asks to commit, save work, or wrap up a task.
---

# Commit Workflow Runbook

You are executing the standardized git commit procedure. Follow these strict steps sequentially:

1. **Verify Test Suite:** Run `run_command` with `python -m pytest` (or the target repo's test command). If any tests fail, **STOP IMMEDIATELY**. Report the failures to the user. Do not commit broken code.
2. **Inspect Changes:** Run `run_command` with `git status -s` and `git diff --staged` to inspect what is actually being modified.
3. **Stage Specific Files:** Ask the user for confirmation before staging, or stage specific target files using `run_command` with `git add <filepath>`. Do NOT run `git add -A` blindly without user consent.
4. **Draft Conventional Commit:** Write a commit message following the specification: `type(scope): summary`.
   - **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
   - Keep the summary line in the imperative mood and under 72 characters.
5. **Request Verification & Commit:** Present the staged file list and the proposed commit message to the user. Once they type `y` or approve, execute `run_command` with `git commit -m "<message>"`.