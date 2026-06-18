# api-specification.md

# Authentication

---

POST

/api/auth/login

Request

email

password

Response

access_token

refresh_token

user

---

POST

/api/auth/refresh

Response

new access token

---

POST

/api/auth/logout

---

# User Management

---

GET

/api/users

List users

---

POST

/api/users

Create user

---

PUT

/api/users/{id}

Update user

---

DELETE

/api/users/{id}

Disable user

---

POST

/api/users/invite

Invite user

---

# Agent APIs

---

POST

/api/agent/planner

Input

prompt

Output

task graph

---

POST

/api/agent/generate

Input

task graph

Output

n8n workflow json

---

POST

/api/agent/explain

Input

workflow

Output

workflow explanation

---

POST

/api/agent/runtime

Input

workflow state

Output

agent decision

---

# Workflow APIs

---

POST

/api/workflows/import

Import generated workflow

---

POST

/api/workflows/validate

Validate generated workflow

---

POST

/api/workflows/explain

Workflow explanation

---

# Health

---

GET

/api/health

Status

OK
