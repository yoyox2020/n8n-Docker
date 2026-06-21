# README.md

# Asuralab Agentic Workflow Engine

## Objective

Build an Agentic Workflow Engine on top of n8n.

Workflow remains the source of truth.

Every AI-generated workflow must be visible and editable.

Core flow:

Prompt
↓
Planner
↓
Task Graph
↓
Workflow Generator
↓
n8n Workflow
↓
Canvas
↓
Editable

---

## Architecture

n8n Fork

Responsibilities

* Authentication
* User Management
* RBAC
* Workflow Engine
* Credentials
* Executions

Agent Service

Responsibilities

* Planner
* Memory
* Runtime
* Tool Registry
* Workflow Generator

Communication

REST API

---

## Project Phases

Phase 0

Remove Registration

Phase 1

Branding
Login
User Management
RBAC

Phase 2

Agent Service
Planner
Memory
Tool Registry

Phase 3

Workflow Generator
Chat To Workflow

Phase 4

Agent Runtime
Human Approval
Agent Node

---

## Documentation Index

| File | Description |
|------|-------------|
| [phase-0-fork.md](phase-0-fork.md) | Phase 0 fork summary |
| [phase-0-fork-rbac-owner-member.md](phase-0-fork-rbac-owner-member.md) | Phase 0 RBAC owner & member |
| [phase-0-fork-delete-owner-Delete.md](phase-0-fork-delete-owner-Delete.md) | Phase 0 owner-only delete |
| [phase-0-fork-halaman-login+logokecil.md](phase-0-fork-halaman-login+logokecil.md) | Phase 0 login page & logo |
| [phase-0-remove-registration.md](phase-0-remove-registration.md) | Phase 0 remove registration |
| [phase-0-update-user-and-ui.md](phase-0-update-user-and-ui.md) | Phase 0 user & UI updates |
| [readme-phase-0-database.md](readme-phase-0-database.md) | Phase 0 database schema |
| [phase-status-phase-1.md](phase-status-phase-1.md) | Phase 1 implementation status |
| [phase-1-type-safety-DTO.md](phase-1-type-safety-DTO.md) | **Phase 1 — Type safety, DTO, custom LLM provider, UI cleanup** |
| [phase-1-to-phase-4.md](phase-1-to-phase-4.md) | Phase 1–4 roadmap |
| [phase-status-overview.md](phase-status-overview.md) | All phases status overview |
| [api-specification.md](api-specification.md) | REST API specification |
| [database-schema.md](database-schema.md) | Full database schema |
| [security-baseline.md](security-baseline.md) | Security baseline |
| [coding-standars.md](coding-standars.md) | Coding standards |
| [Roadmap.md](Roadmap.md) | Project roadmap |

---

## Rules

Do not rewrite n8n.

Modify only what is required.

Keep AI outside n8n.

Keep workflow editable.

Workflow remains the source of truth.
