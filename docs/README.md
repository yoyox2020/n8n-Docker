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

## Rules

Do not rewrite n8n.

Modify only what is required.

Keep AI outside n8n.

Keep workflow editable.

Workflow remains the source of truth.
