# database-api-security-roadmap.md

# DATABASE

---

n8n Database

Existing

user

workflow_entity

credentials_entity

execution_entity

shared_workflow

shared_credentials

---

Modifications

Add Role Support

Owner

Admin

Editor

Viewer

---

No Separate SaaS Database

---

Agent Service Database

PostgreSQL

Stores

Conversation History

Workflow History

Agent Decisions

---

# API

---

Authentication

POST /api/auth/login

POST /api/auth/logout

POST /api/auth/refresh

---

Users

GET /api/users

POST /api/users

PUT /api/users/{id}

DELETE /api/users/{id}

---

Agent

POST /api/agent/planner

POST /api/agent/generate

POST /api/agent/explain

POST /api/agent/runtime

---

Workflow

POST /api/workflows/import

POST /api/workflows/validate

---

# SECURITY

---

Password

bcrypt

---

Tokens

Access Token

15 Minutes

Refresh Token

7 Days

---

Encrypt

API Keys

OAuth Tokens

Secrets

---

Encryption

AES-256

---

Audit

Login

Workflow Changes

Credential Changes

Agent Decisions

---

# ROADMAP

---

Sprint 1

Remove Registration

Auto Create Owner

Login Directly

---

Sprint 2

Branding

Roles

User Management

---

Sprint 3

Agent Service Skeleton

Planner

Memory

Tool Registry

---

Sprint 4

Workflow Generator

Workflow Import

---

Sprint 5

Chat To Workflow

Agent Builder Panel

---

Sprint 6

Agent Runtime

Agent Node

Human Approval

---

MVP Complete

User Management

Workflow Builder

Chat To Workflow

Agent Runtime

Editable Workflow
