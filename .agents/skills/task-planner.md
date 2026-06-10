---
name: task-planner
description: Breaks product or engineering work into ordered, implementable tasks. Use when requirements are too large, vague, risky, or multi-step. Use before implementation when a plan, sequencing, dependencies, acceptance criteria, or parallelization strategy is needed.
---

# Task Planner

## Overview

Convert requirements into a clear implementation plan. The output should help an engineer or coding agent start work without guessing what to do next.

Planning is read-only. Do not write implementation code while planning.

## Instruction Priority

Project-specific instructions have higher priority than this skill.

When planning work in a repository, always check and follow:

1. `AGENTS.md`
2. Canonical project documentation
3. Existing architecture and codebase conventions
4. This skill

If this skill conflicts with `AGENTS.md`, canonical documentation, or established repository patterns, follow the project-specific source instead.

## When to Use

Use this skill when:

- A feature is too large to implement directly
- Requirements need sequencing
- The work spans frontend, backend, database, infrastructure, or tests
- Dependencies between tasks are unclear
- Work may be parallelized
- Risks or unknowns need to be surfaced
- A human needs a clear scope breakdown

Do not use this skill for trivial single-file changes with obvious scope.

## Planning Process

### 1. Understand the Goal

Identify:

- What is being built or changed
- Who the user is
- What behavior must exist after the work is complete
- What constraints are known
- What is explicitly out of scope

If requirements are incomplete, make reasonable assumptions and list them.

### 2. Inspect Existing Context

Before planning implementation, inspect:

- Relevant code structure
- Existing patterns
- Existing APIs or models
- Existing tests
- Existing conventions
- Similar completed features

Do not plan against an imaginary architecture.

### 3. Identify Dependencies

Map what must exist before other work can proceed.

Typical dependency order:

1. Data model or contract
2. Backend validation and business logic
3. API endpoint or interface
4. Client/API integration
5. UI or consumer behavior
6. Tests and quality checks
7. Documentation or rollout steps

Prefer dependency-aware plans over arbitrary task lists.

### 4. Slice Work Vertically Where Possible

Prefer small end-to-end slices that leave the system working.

Bad:

- Build all database changes
- Build all backend endpoints
- Build all frontend screens
- Connect everything at the end

Better:

- Implement one complete user-visible capability
- Verify it
- Then implement the next capability

Vertical slices reduce integration risk.

### 5. Define Acceptance Criteria

Every task must have testable acceptance criteria.

Good acceptance criteria are:

- Specific
- Observable
- Verifiable
- Small enough to complete in one focused work session

Avoid vague criteria like "works correctly" or "improve UX."

### 6. Define Verification

Each task should include how to verify it:

- Unit tests
- Integration tests
- Typecheck
- Lint
- Build
- Manual scenario
- API call
- Screenshot or UI check, if relevant

Verification should be executable by another agent or engineer.

## Task Format

Use this format:

```markdown
## Task N: Short imperative title

**Description:** One paragraph explaining what this task accomplishes.

**Acceptance criteria:**
- [ ] Specific, testable condition
- [ ] Specific, testable condition
- [ ] Specific, testable condition

**Verification:**
- [ ] Command or test to run
- [ ] Manual check, if needed

**Dependencies:** Task numbers or "None"

**Likely files or areas:**
- `path/or/module`
- `path/or/module`

**Scope:** XS / S / M / L
```

## Task Sizing

Use these sizes:

- XS: one small function, config, or copy change
- S: one file or one isolated behavior
- M: one coherent feature slice across a few files
- L: broad change that should probably be split
- XL: too large; must be broken down

Prefer S and M tasks.

Break a task down further if:

- It has more than three acceptance criteria
- The title contains "and"
- It touches unrelated subsystems
- It cannot be verified independently
- It would leave the system broken until a later task

## Plan Output Template

```markdown
# Implementation Plan: [Name]

## Goal

[Concise description of the intended outcome.]

## Assumptions

- [Assumption 1]
- [Assumption 2]

## Architecture Notes

- [Relevant existing pattern]
- [Important design decision]
- [Boundary or contract to preserve]

## Tasks

### Phase 1: Foundation

[Tasks]

### Phase 2: Core Implementation

[Tasks]

### Phase 3: Quality and Finish

[Tasks]

## Checkpoints

- [ ] After Phase 1: tests/build still pass
- [ ] After Phase 2: core flow works end-to-end
- [ ] Before completion: quality review completed

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---:|---|
| [Risk] | High/Medium/Low | [Mitigation] |

## Open Questions

- [Question]
```

## Completion Checklist

Before finalizing the plan:

- [ ] Tasks are ordered by dependency
- [ ] Each task has acceptance criteria
- [ ] Each task has verification steps
- [ ] Large tasks were split
- [ ] Risks are explicit
- [ ] Unknowns are listed
- [ ] The plan can be executed by another engineer or agent
