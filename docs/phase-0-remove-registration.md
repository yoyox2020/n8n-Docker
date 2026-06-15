# phase-0-remove-registration.md

# Goal

Users should never see n8n setup wizard.

---

Current Flow

Install
↓
Create Owner
↓
Login

---

Target Flow

Provision Tenant
↓
Create Owner Automatically
↓
Login

---

Scope

Remove

* Owner Registration
* Owner Setup Wizard

Keep

* Login
* Forgot Password
* User Invitation

---

Database

Use existing n8n database.

Do not create a new authentication database.

Use existing user table.

---

Provisioning

Step 1

Create database

Step 2

Run n8n migrations

Step 3

Create owner user

Step 4

Generate password

Step 5

Send credentials

---

Success Criteria

Owner can login immediately.

No registration page exists.
