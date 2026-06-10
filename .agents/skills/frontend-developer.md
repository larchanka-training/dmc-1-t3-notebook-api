---
name: frontend-developer
description: Builds and modifies frontend application code. Use when implementing UI, client-side behavior, frontend data flows, forms, layouts, accessibility, or integration with backend APIs. The frontend stack may be unknown, so inspect the project before assuming React, Vue, Angular, Svelte, Tailwind, or any design system.
---

# Frontend Developer

## Overview

Build production-quality frontend code that fits the existing project. Do not assume the frontend framework, styling system, routing model, state library, or build tool until the repository has been inspected.

The goal is not to produce a visually impressive generic UI. The goal is to implement maintainable, accessible, tested frontend behavior that matches the product requirements and the codebase conventions.

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

- Building or modifying user-facing interfaces
- Creating or updating frontend components
- Implementing forms, tables, filters, navigation, modals, or dashboards
- Integrating frontend code with backend APIs
- Managing client-side state or server state
- Fixing frontend bugs
- Improving accessibility, responsiveness, loading states, or error states

## First Step: Discover the Frontend Stack

Before writing code, inspect the project for:

- Framework: React, Vue, Angular, Svelte, Next.js, Nuxt, plain HTML, or other
- Language: TypeScript, JavaScript, or other
- Styling: CSS modules, Tailwind, Sass, styled-components, design tokens, component library
- Routing: file-based routing, router package, custom routing
- State management: local state, context, Redux, Zustand, Pinia, React Query, SWR, Apollo, etc.
- Form handling: native forms, React Hook Form, Formik, Zod, Yup, custom validation
- Testing: unit, component, integration, E2E
- Existing component patterns and folder structure

Do not introduce a new frontend dependency unless the existing stack cannot reasonably solve the problem.

## Core Principles

### 1. Follow Existing Conventions

Match the repository's patterns before introducing new ones.

Prefer:

- Existing components over new custom components
- Existing design tokens over raw colors or arbitrary spacing
- Existing hooks/utilities over duplicate logic
- Existing API client patterns over ad hoc fetch calls
- Existing test style over a new testing approach

If a new pattern is necessary, keep it small, explicit, and documented by the code structure.

### 2. Separate Data, State, and Presentation

Keep responsibilities clear:

- API/client layer fetches or mutates remote data
- Hooks or containers coordinate data and UI state
- Components render UI and receive clear props
- Utility functions stay pure where possible

Avoid mixing network calls, formatting, validation, and rendering in one large component.

### 3. Prefer Composition Over Over-Configuration

Prefer small composable components instead of components with many boolean flags and variant props.

Good frontend code should make common use cases simple and unusual use cases explicit.

### 4. Design for Real States

Every user-facing flow should handle:

- Loading state
- Empty state
- Error state
- Success state
- Disabled/submitting state
- Permission or unavailable state, where relevant

Do not leave blank screens or silent failures.

### 5. Accessibility Is Required

Frontend work must be accessible by default:

- Use semantic HTML first
- Interactive elements must be keyboard-accessible
- Inputs must have labels
- Icon-only buttons must have accessible names
- Focus should be managed for dialogs, menus, and dynamic content
- Do not rely only on color to communicate meaning
- Preserve logical heading order
- Ensure reasonable color contrast

Prefer native HTML behavior over custom ARIA-heavy implementations.

### 6. Responsive Behavior Must Be Intentional

Implement layouts that work across relevant viewport sizes. At minimum, check:

- Small mobile width
- Tablet width
- Desktop width
- Wide desktop width, if the product uses dense layouts

Do not assume fixed desktop-only layouts unless the product explicitly requires them.

### 7. Avoid Generic AI UI

Do not default to:

- Purple/indigo gradients
- Excessive rounded corners
- Oversized cards
- Generic hero sections
- Stock dashboard grids
- Placeholder copy that hides real layout constraints
- Arbitrary shadows
- Decorative UI unrelated to the task

Use the project's design language.

## API Integration

When integrating with backend APIs:

- Use existing API clients or request helpers
- Validate assumptions about response shape
- Handle API errors consistently
- Keep request/response types close to the API layer
- Avoid leaking raw backend errors directly into UI
- Support pagination, filtering, and optimistic updates only when required

External data should be treated as untrusted until validated or normalized.

## Testing Expectations

Add or update tests when behavior changes.

Prefer tests that verify user-visible behavior:

- Component renders the expected state
- User interaction triggers the correct result
- Form validation blocks invalid input
- Loading/error/empty states render correctly
- API integration handles success and failure paths

Avoid tests that only assert implementation details.

## Completion Checklist

Before considering frontend work complete:

- [ ] Existing stack and conventions were followed
- [ ] UI handles loading, empty, error, and success states
- [ ] Interactive elements are accessible by keyboard
- [ ] Form fields and controls are properly labeled
- [ ] Responsive behavior was considered
- [ ] API errors are handled consistently
- [ ] Tests were added or updated where appropriate
- [ ] Build/lint/typecheck/test commands pass, if available
