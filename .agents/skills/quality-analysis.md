---
name: quality-analysis
description: Performs independent quality analysis of implemented work. Use after implementation and before review or merge to check correctness, test coverage, risks, regressions, maintainability, security, performance, and readiness.
---

# Quality Analysis

## Overview

Analyze whether implemented work is actually ready. This skill is not for writing the implementation and not for reviewing PR style. It is for independent verification of quality, risk, and completeness.

The output should identify what is verified, what is unverified, what is risky, and what must be fixed before the work can be considered complete.

## Instruction Priority

Project-specific instructions have higher priority than this skill.

When working in a repository, always check and follow:

1. `AGENTS.md`
2. Canonical project documentation
3. Existing codebase conventions
4. This skill

If this skill conflicts with `AGENTS.md`, canonical documentation, or established repository patterns, follow the project-specific source instead.

## When to Use

Use this skill when:

- A feature implementation is complete
- A bug fix needs validation
- Generated code needs independent checking
- A task claims to be done
- You need to assess test coverage
- You need a readiness report before PR review
- You suspect regressions, missing edge cases, or hidden risks

## Quality Dimensions

Analyze the work across these dimensions.

### 1. Requirement Fit

Check whether the implementation matches the requested behavior.

Ask:

- Does it solve the stated problem?
- Are all acceptance criteria satisfied?
- Did the implementation add unrelated behavior?
- Did it miss any explicit requirement?
- Are assumptions documented?

### 2. Correctness

Check whether the behavior is logically correct.

Look for:

- Edge cases
- Empty/null/missing values
- Boundary conditions
- Race conditions
- State inconsistencies
- Incorrect error handling
- Incorrect default values
- Timezone/date issues
- Pagination or filtering mistakes
- Data loss or partial update bugs

### 3. Test Coverage

Evaluate whether tests prove the behavior.

Check:

- Are there tests for the main success path?
- Are there tests for failure paths?
- Are edge cases covered?
- Would the tests fail if the implementation were broken?
- Are tests too coupled to implementation details?
- Are backend and frontend integration points tested where needed?
- Are regression tests included for bug fixes?

Do not claim something is tested unless there is evidence.

### 4. Maintainability

Check whether the code will be easy to change later.

Look for:

- Large functions or components
- Duplicated logic
- Unclear names
- Hidden side effects
- Over-generalized abstractions
- Tight coupling
- Inconsistent patterns
- Dead code
- Comments explaining obvious code instead of intent

### 5. Security

Check whether the implementation creates security risk.

Look for:

- Missing validation
- Missing authorization
- Trusting client input
- Secret leakage
- Unsafe logging
- Unsafe file handling
- Injection risks
- XSS risks
- Overexposed data
- Unsafe external API handling

### 6. Performance and Scalability

Check whether the implementation may degrade under realistic use.

Look for:

- N+1 queries
- Unbounded list fetching
- Missing pagination
- Repeated expensive computation
- Blocking I/O in async paths
- Excessive frontend re-renders
- Large client bundles
- Inefficient loops over large data
- Missing indexes for new query patterns

### 7. Operational Readiness

Check whether the change can run safely in real environments.

Look for:

- Required environment variables
- Migration order
- Backward compatibility
- Rollback concerns
- Logging and observability
- Error monitoring
- Feature flags, if relevant
- Deployment sequencing

## Analysis Process

### Step 1: Identify the Claimed Scope

Summarize what the implementation claims to do.

### Step 2: Compare Against Requirements

Map requirements to evidence in code and tests.

### Step 3: Inspect Risk Areas

Focus on changed boundaries:

- API contracts
- Database writes
- Authentication/authorization
- External integrations
- User-visible flows
- Async/background behavior
- Error paths

### Step 4: Verify Tests and Commands

Check what verification was run or can be run.

If commands are unavailable, state that clearly.

### Step 5: Produce a Readiness Judgment

Use one of:

- **Ready:** No blocking issues found
- **Ready with caveats:** Minor risks remain, but no blockers
- **Not ready:** Blocking correctness, security, test, or operational issues exist

## Output Format

```markdown
# Quality Analysis: [Change/Feature Name]

## Readiness

Ready / Ready with caveats / Not ready

## Summary

[Brief assessment of implementation quality.]

## Verified

- [What is supported by code, tests, or commands]
- [What was checked directly]

## Issues

### Critical

- [Issue that blocks release or merge]

### Important

- [Issue that should be fixed before completion]

### Minor

- [Non-blocking improvement]

## Test Coverage

**Covered:**
- [Covered behavior]

**Missing or weak:**
- [Untested behavior]

## Risks

| Risk | Impact | Recommendation |
|---|---:|---|
| [Risk] | High/Medium/Low | [Recommendation] |

## Recommended Next Actions

1. [Most important fix or verification]
2. [Next action]
3. [Next action]
```

## Rules

- Do not rubber-stamp.
- Do not invent verification that was not performed.
- Distinguish evidence from assumptions.
- Prefer concrete findings over vague concerns.
- If the implementation is good, say so directly.
- If it is not ready, state the blockers clearly.
