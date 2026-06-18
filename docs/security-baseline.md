# security-baseline.md

# Authentication

---

Password Hash

bcrypt

---

Access Token

15 Minutes

---

Refresh Token

7 Days

---

# Credential Security

Encrypt

API Keys

OAuth Tokens

Webhook Secrets

---

Encryption

AES-256

---

# API Security

Rate Limit

100 Requests Per Minute

---

Require Authentication

All

/api/*

---

# User Security

Owner Can

Create User

Disable User

Change Role

---

Admin Cannot

Delete Owner

Change Billing

---

# Agent Security

Agent Cannot Execute

Delete Workflow

Delete Credential

Delete User

Without Approval

---

# Approval Required

Workflow Deletion

Credential Deletion

Mass Update

Mass Delete

---

# Audit Logging

Track

Login

Logout

Workflow Change

Credential Change

Agent Decision

User Management

---

# Security Principle

Human Approval Required

For Destructive Actions

Agent Assists

Human Decides
