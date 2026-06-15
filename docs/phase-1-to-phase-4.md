# phase-1-to-phase-4.md

# PHASE 1

SaaS Foundation

---

Branding

Replace

n8n

with

Asuralab Workflow

Replace

* Logo
* Favicon
* Browser Title

---

Authentication

Email
Password

Password Hash

bcrypt

---

Roles

Owner

Admin

Editor

Viewer

---

Owner

Manage Users

Manage Workflows

Manage Credentials

---

Admin

Manage Workflows

Manage Credentials

---

Editor

Create Workflow

Edit Workflow

Execute Workflow

---

Viewer

Read Only

---

User Management

Create User

Invite User

Disable User

Change Role

---

PHASE 2

Agent Service

---

Stack

FastAPI

PostgreSQL

Redis

---

Repository

agent-service

api/

planner/

memory/

runtime/

tools/

workflow-generator/

---

Planner

Input

Prompt

Output

Task Graph

---

Example

Prompt

Save invoice attachment to Google Drive and notify WhatsApp

Task Graph

Email Trigger
↓
Extract Attachment
↓
Upload Drive
↓
Send WhatsApp

---

Memory

Store

Conversation History

Workflow History

---

Tool Registry

gmail

whatsapp

http

postgres

jira

slack

---

PHASE 3

Chat To Workflow

---

Flow

Prompt
↓
Planner
↓
Task Graph
↓
Workflow Generator
↓
Workflow JSON
↓
Import To n8n
↓
Canvas

---

Workflow Generator

Convert

Task Graph

into

n8n Workflow JSON

---

UI

Agent Builder Panel

---

Actions

Generate

Explain

Regenerate

---

Result

Visual Workflow

Editable Workflow

---

PHASE 4

Agent Runtime

---

Goal

Allow workflow to make runtime decisions.

---

Agent Node

Node inside n8n.

---

Execution Flow

Workflow
↓
Agent Node
↓
Agent Service
↓
Decision
↓
Workflow

---

Runtime Components

Planner

Memory

Tools

---

Approval

Human approval required for sensitive actions.

---

Result

Workflow remains visible.

Workflow remains editable.

Agent assists workflow execution.
