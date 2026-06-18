# MST Workflow

Enterprise Agentic Workflow Platform powered by Mistika.

Built on top of n8n and extended with Agent Services, Chat-to-Workflow Generation, and Runtime Decision Making.

---

# Vision

Transform traditional workflow automation into an intelligent workflow platform where:

* Users can build workflows visually.
* AI can generate workflows from natural language.
* Agents can assist workflow execution.
* Human users remain in control.

---

# Product Roadmap

## Phase 0

Fork n8n and prepare platform foundation.

### Objectives

* Fork n8n source code
* Remove unnecessary AI model providers
* Integrate Mistika as primary AI provider
* Establish development architecture
* Prepare branding assets

### Deliverables

* MST Workflow repository
* Mistika integration foundation
* Development environment ready

---

# Phase 1

## SaaS Foundation

### Goal

Transform n8n into a multi-user SaaS platform.

---

## Branding

Replace all n8n branding with MST Workflow.

### Components

* Logo			= done
* Favicon		= done
* Browser Title		= done
* Login Page		= done
* Dashboard Branding	= done

---

## Authentication

### Supported

* Email			= done
* Password		= done

### Password Storage

bcrypt			= done

---

## Roles

### Owner

Permissions:

* Manage Users		= audit
* Manage Workflows	= audit
* Manage Credentials	= audit
* Manage Workspace	= audit

---

### Admin

Permissions:

* Manage Workflows	= audit
* Manage Credentials	= audit

---

### Editor

Permissions:

* Create Workflow
* Edit Workflow
* Execute Workflow

---

### Viewer

Permissions:

* Read Only Access

---

## User Management

### Features

* Create User
* Invite User
* Disable User
* Change Role

---

## Deliverables

### Backend

* Authentication
* Authorization
* User Management

### Frontend

* Login
* User Management
* Role Management

---

# Phase 2

## Agent Service

### Goal

Build an external AI service responsible for planning, memory, and workflow generation.

Agent Service remains independent from n8n.

---

## Technology Stack

### API

FastAPI

### Database

PostgreSQL

### Cache

Redis

---

## Repository Structure

agent-service/

api/

planner/

memory/

runtime/

tools/

workflow-generator/

---

## Planner

### Input

Natural Language Prompt

### Output

Task Graph

---

### Example

Prompt:

Save invoice attachment to Google Drive and notify WhatsApp

Output:

Email Trigger
↓
Extract Attachment
↓
Upload Drive
↓
Send WhatsApp

---

## Memory

Store:

* Conversation History
* Workflow History
* Planning History

---

## Tool Registry

Supported tools:

* Gmail
* WhatsApp
* HTTP
* PostgreSQL
* Jira
* Slack

---

## Deliverables

* Planner Service
* Memory Service
* Tool Registry
* Runtime Foundation

---

# Phase 3

## Chat To Workflow

### Goal

Allow users to generate workflows using natural language.

---

## Flow

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
Import To MST Workflow
↓
Canvas

---

## Workflow Generator

Convert:

Task Graph

into

n8n Workflow JSON

---

## Example

User Prompt:

When invoice email arrives, save attachment to Google Drive and send WhatsApp notification.

Generated Task Graph:

Email Trigger
↓
Extract Attachment
↓
Upload Drive
↓
Send WhatsApp

Generated Output:

n8n Workflow JSON

Automatically imported into canvas.

---

## UI

### Agent Builder Panel

Actions:

* Generate
* Explain
* Regenerate

---

## Result

Users receive:

* Visual Workflow
* Editable Workflow
* Production-ready Workflow

---

## Deliverables

* Agent Builder UI
* Workflow Generator
* Canvas Integration
* Workflow Import Engine

---

# Phase 4

## Agent Runtime

### Goal

Allow workflows to make runtime decisions using AI.

---

## Agent Node

Special node available inside MST Workflow.

---

## Execution Flow

Workflow
↓
Agent Node
↓
Agent Service
↓
Decision
↓
Workflow Continues

---

## Runtime Components

### Planner

Determines next action.

### Memory

Provides execution context.

### Tools

Allows external interaction.

---

## Human Approval

Required for sensitive operations.

Examples:

* Delete Records
* Financial Transactions
* Credential Changes
* Production Changes

---

## Result

Workflows remain:

* Visual
* Editable
* Auditable

Agent assists execution rather than replacing workflows.

---

# High Level Architecture

User
↓
MST Workflow
↓
Workflow Engine
↓
Agent Node
↓
Agent Service
↓
Mistika Router
↓
Decision

---

# Core Principle

Workflow is still the source of truth.

Agent enhances workflows.

Agent does not replace workflows.

Users can always inspect, edit, and govern automation.

---

# Long-Term Vision

MST Workflow becomes an enterprise platform combining:

* Workflow Automation
* Agentic AI
* Human Approval
* Visual Workflow Design
* Chat To Workflow
* Runtime Decision Making

while maintaining governance, visibility, and operational control.
