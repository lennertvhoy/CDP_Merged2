# CDP_Merged Azure Architecture

**Platform:** Azure  
**Last Updated:** 2026-03-03  
**Status:** Canonical production target

## Executive Summary

CDP_Merged is a **privacy-bounded, PostgreSQL-backed CDP architecture** running on Azure.

- **Source systems** remain the PII and operational master-record layer
- **PostgreSQL** is the customer-intelligence and analytical truth layer
- **Tracardi** is the projected event/workflow/activation runtime
- **The AI chatbot** must query PostgreSQL for authoritative answers

This is the architecture future implementation should converge toward. If code or older docs differ from this document, verify implementation first and record the gap in the root workflow docs before proceeding.

## Truth Layers

### Source Systems

Source systems such as Teamleader, Exact, Autotask, websites, and campaign providers remain the systems that own private contact details and operational records.

- resolve names, emails, phones, and similar PII there
- treat the CDP as a UID-driven intelligence and activation stack
- re-link UID to PII only when the user is authorized and the workflow requires it

### PostgreSQL

PostgreSQL is the **customer-intelligence and analytical truth layer**.

- public and business master data
- UID and identity bridge across systems
- enrichment outputs and provenance
- behavioral aggregates and analytical facts
- AI decisions and tag provenance
- consent and suppression state
- canonical segment definitions and memberships
- audit-friendly business state for the chatbot

### Tracardi

Tracardi is the **projected activation runtime**.

- event ingestion
- real-time workflow triggers
- projected score and tag updates
- campaign and activation orchestration
- operational projections of selected profiles, events, and audiences

Tracardi is **not** the canonical broad historical query layer and **not** the analytical system of record for the full CDP.

### AI Chatbot

The chatbot should:

- translate natural language into deterministic PostgreSQL-backed search, count, analytics, and 360 queries
- use the LLM for intent classification, filter extraction, clarification, and summarization
- preview and explain segment logic before mutating actions
- call Tracardi only when the user wants operational actions such as workflow execution, segment projection, or campaign activation
- avoid free-form production SQL generation or authoritative factual answers from Tracardi

## Architecture Principles

### 1. Qualify Truth Layers Explicitly

Do not use the phrase "source of truth" without qualifying which layer you mean:

- source systems = PII and operational master truth
- PostgreSQL = customer-intelligence and analytical truth
- Tracardi = activation/runtime projection

### 2. Canonical Facts Land In PostgreSQL

Canonical business data, analytical facts, and durable AI outputs land in PostgreSQL first. Downstream systems receive projections, not ownership.

### 3. Activation Is Downstream

Tracardi, Resend, Flexmail, and similar tools execute against canonical state rather than becoming the canonical state.

### 4. Deterministic Accuracy Over Prompt Complexity

High accuracy comes from typed tools, validated filters, explicit previews, and authoritative data access. Prompt complexity alone is not the answer.

### 5. Privacy By Design

Identity mapping, consent, and sensitive joins should be controlled in the canonical data layer. Event and activation systems should only receive the minimum operational slice they need.

### 6. Contradictions Must Be Resolved

If docs conflict:

1. check code and deployed configuration
2. check logs and provider/runtime state
3. update current root docs
4. only then continue with implementation work

## High-Level Data Flow

```text
Source systems and public datasets
  -> canonical ingestion and normalization
  -> PostgreSQL analytical truth layer
  -> enrichment, scoring, and AI decision recording
  -> semantic views / parameterized query tools
  -> chatbot answers facts from PostgreSQL only
  -> projected segments/events/traits
  -> Tracardi workflows and activation
  -> Resend / Flexmail / other downstream channels
  -> webhook and campaign event return
  -> PostgreSQL first, then optional Tracardi operational update
```

## Production Domain Model Direction

The architecture is not just a KBO search stack. The production CDP should model:

- organizations and account hierarchy
- contacts and role relationships
- source-system identities
- invoices, subscriptions, and commercial history
- tickets, support interactions, and operational workload
- campaign sends, deliveries, opens, clicks, and bounces
- website and product usage behavior
- consent, suppression, and compliance state
- computed traits, scores, AI decisions, and next-best-action outputs

## Mandatory Production Patterns

### 1. Analytical Tags Must Be Durable Facts

If a tag, score, or trait matters for chatbot answers or canonical segments, it must exist in PostgreSQL with provenance. Tracardi may hold the projected runtime copy, but not the only copy.

### 2. Segments Are Canonical Outside Tracardi

Segment logic belongs in SQL or explicit metadata stored outside Tracardi. Tracardi receives segment state for activation.

### 3. Mutations Write To PostgreSQL First

If the chatbot or an operator changes a segment, score, or business state:

1. write the canonical change to PostgreSQL
2. emit the operational update to Tracardi or another downstream system
3. record the action in audit logs

### 4. Prefer Need-Based Tracardi Projection

Do not bulk-project the entire KBO universe into Tracardi by default. Prefer lazy or need-based profile creation for active or activation-relevant UIDs unless a verified requirement justifies broader projection.

### 5. Keep Raw Unstructured PII Out Of Tracardi

The intelligence layer may analyze private unstructured data upstream, but Tracardi should receive only the derived tags, scores, and references it operationally needs.

### 6. Keep Operational Logs UID-First

Conversation logs, audit logs, tool traces, and query logs should use UIDs or controlled references rather than names, emails, or phones wherever feasible. If a user-facing response needs PII, resolve it only in an authorized presentation or activation step.

### 7. Reconcile Identity Merges In PostgreSQL First

If Teamleader or another source system merges or splits records, repair the canonical UID bridge in PostgreSQL first. Only after that reconciliation should downstream projections, Tracardi profile links, and activation audiences be updated.

### 8. Resolve Delivery PII At Activation Time

Downstream campaign or delivery tools should receive the minimum operational payload needed to execute. Prefer resolving destination email or phone data from the source system or a controlled API at authorized send time instead of treating downstream tools as the permanent PII store.

## Current Implementation Gap

As of 2026-03-03, the codebase still has a major mismatch:

- the large KBO import completed into PostgreSQL
- the chatbot search tool still uses Tracardi/TQL as its primary backend
- historical docs mention a Tracardi-to-PostgreSQL sync path, but the current repo audit did not find a live implementation file for it
- no current `profile_tags` or `ai_decisions` model was found in the targeted repo audit

That gap is the highest-priority architecture task. Until it is fixed, the repo should not claim that the chatbot is already using the canonical data plane for authoritative answers.

## What Tracardi Should Still Be Used For

- event-driven scoring
- workflow automation
- audience activation
- campaign and engagement triggers
- near-real-time operational reactions

## What Should Move Away From Tracardi

- authoritative counts across the full business dataset
- broad historical analytics
- master entity storage
- canonical segment definitions
- core identity-resolution logic

## Implementation Priorities

1. Refactor the chatbot search/count/analytics path to PostgreSQL-backed joined retrieval.
2. Verify enrichment completeness and field quality in PostgreSQL.
3. Persist analytically relevant tags, scores, and AI decisions to PostgreSQL with provenance.
4. Define canonical segment storage and projection rules into Tracardi.
5. Standardize campaign event writeback into PostgreSQL first.
6. Add identity-merge reconciliation rules for the canonical UID bridge and downstream projections.
7. Enforce UID-first logging and activation-time PII resolution across chatbot and campaign flows.
8. Add audit, approval, and explainability around mutating chatbot actions.
