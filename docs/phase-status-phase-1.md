# Phase 1 — Status Implementasi

> Dokumen ini mencatat semua perubahan Phase 1 yang telah dilakukan.
> Terakhir diupdate: 2026-06-18

---

## Ringkasan Status

| Kategori | Item | Status | File |
|----------|------|--------|------|
| **Branding** | Logo | ✅ Done (sebelumnya) | `MainSidebarHeader.vue`, `mst-logo.svg` |
| | Favicon | ✅ Done | `public/favicon.svg`, `index.html` |
| | Browser Title | ✅ Done | `index.html` |
| | Login Page | ✅ Done (sebelumnya) | `SigninView.vue` |
| | Dashboard Branding | ✅ Done (sebelumnya) | `MainSidebarHeader.vue` |
| **Auth** | Email + Password | ✅ Done | Built-in n8n |
| | bcrypt | ✅ Done | Built-in n8n |
| **Role** | Owner | ✅ Done | License bypass |
| | Admin | ✅ Done | `license-state.ts` + `settings.store.ts` |
| | Editor (workflow) | ✅ Done | `workflow-sharing-scopes.ee.ts` (existing) |
| | Viewer (workflow) | ✅ Done | `workflow-sharing-scopes.ee.ts` (baru) |
| | Editor (project) | ✅ Done | License bypass `isProjectRoleEditorLicensed` |
| | Viewer (project) | ✅ Done | License bypass `isProjectRoleViewerLicensed` |
| **User Mgmt** | Create + Invite | ✅ Done | `invitation.controller.ts` |
| | Invite Admin | ✅ Done | License bypass `isAdvancedPermissionsLicensed` |
| | Disable User | ✅ Done | Backend + frontend baru |
| | Change Role | ✅ Done | Existing + Admin role sekarang aktif |

**Phase 1: 100% Selesai ✅**

---

## Detail Perubahan

### 1. Browser Title

**File:** `packages/frontend/editor-ui/index.html`

```html
<!-- SEBELUM -->
<title>n8n.io - Workflow Automation</title>

<!-- SESUDAH -->
<title>MST Workflow</title>
```

---

### 2. Favicon MST

**File baru:** `packages/frontend/editor-ui/public/favicon.svg`

SVG minimalis — huruf "M" putih di kotak biru (#1A56DB, radius 6px, 32×32).

**File diupdate:** `packages/frontend/editor-ui/index.html`

```html
<!-- SESUDAH -->
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="alternate icon" href="/favicon.ico" />
```

Browser modern (Chrome, Firefox, Edge) menggunakan SVG. `favicon.ico` sebagai fallback untuk browser lama.

---

### 3. Admin Role — License Bypass

**File:** `packages/@n8n/backend-common/src/license-state.ts`

```typescript
// SEBELUM
isAdvancedPermissionsLicensed() {
    return this.isLicensed('feat:advancedPermissions');
}

// SESUDAH
isAdvancedPermissionsLicensed() {
    return true;
}
```

Sebelumnya, undang user sebagai Admin gagal dengan:
`ForbiddenError: Cannot invite admin user without advanced permissions`

---

### 4. Project Role Licenses — Bypass

**File:** `packages/@n8n/backend-common/src/license-state.ts`

```typescript
// Semua tiga diubah ke return true
isProjectRoleAdminLicensed() { return true; }
isProjectRoleEditorLicensed() { return true; }
isProjectRoleViewerLicensed() { return true; }
```

Sebelumnya, assign `project:admin`, `project:editor`, `project:viewer` di team project memerlukan enterprise license.

---

### 5. Advanced Permissions Frontend — Bypass

**File:** `packages/frontend/editor-ui/src/app/stores/settings.store.ts`

```typescript
// SEBELUM
const isEnterpriseFeatureEnabled = computed(() => ({
    ...(settings.value.enterprise ?? {}),
    sharing: true,
}));

// SESUDAH
const isEnterpriseFeatureEnabled = computed(() => ({
    ...(settings.value.enterprise ?? {}),
    sharing: true,
    advancedPermissions: true,
}));
```

Memastikan UI menampilkan Admin role sebagai aktif (bukan disabled/grayed out) di dropdown role management.

---

### 6. Workflow Viewer Role — Baru

**File:** `packages/@n8n/permissions/src/roles/scopes/workflow-sharing-scopes.ee.ts`

```typescript
export const WORKFLOW_SHARING_VIEWER_SCOPES: Scope[] = [
    'workflow:read',
    'workflow:export',
    'workflow:execute-chat',
];
```

**File:** `packages/@n8n/permissions/src/schemas.ee.ts`

```typescript
// SEBELUM
export const workflowSharingRoleSchema = z.enum(['workflow:owner', 'workflow:editor']);

// SESUDAH
export const workflowSharingRoleSchema = z.enum(['workflow:owner', 'workflow:editor', 'workflow:viewer']);
```

**File:** `packages/@n8n/permissions/src/roles/role-maps.ee.ts`

```typescript
export const WORKFLOW_SHARING_SCOPE_MAP = {
    'workflow:owner': WORKFLOW_SHARING_OWNER_SCOPES,
    'workflow:editor': WORKFLOW_SHARING_EDITOR_SCOPES,
    'workflow:viewer': WORKFLOW_SHARING_VIEWER_SCOPES,  // baru
};
```

**File:** `packages/@n8n/permissions/src/roles/all-roles.ts`

Ditambahkan `'workflow:viewer'` ke `ROLE_NAMES` dan `ROLE_DESCRIPTIONS`.

**Efek:** Role `workflow:viewer` akan di-sync ke DB saat n8n startup (via `syncRoles`).

---

### 7. Frontend Share Modal — Viewer

**File:** `packages/frontend/editor-ui/src/app/components/WorkflowShareModal.ee.vue`

```typescript
const workflowRoleTranslations = computed(() => ({
    'workflow:editor': i18n.baseText('workflows.shareModal.role.editor'),
    'workflow:viewer': i18n.baseText('workflows.shareModal.role.viewer'),  // baru
    'workflow:owner': '',
}));
```

**File:** `packages/frontend/@n8n/i18n/src/locales/en.json`

```json
"workflows.shareModal.role.viewer": "@:_reusableBaseText.roles.viewer",
"workflows.roles.viewer": "@:_reusableBaseText.roles.viewer"
```

---

### 8. Disable User — Fitur Baru

**Backend — `packages/cli/src/controllers/users.controller.ts`**

Endpoint baru: `PATCH /users/:id/disabled`

```typescript
@Patch('/:id/disabled')
@GlobalScope('user:update')
async toggleUserDisabled(req, _res, @Param('id') id, @Body { disabled }) {
    // Validasi: tidak bisa disable diri sendiri, tidak bisa disable instance owner
    await this.userRepository.update(id, { disabled: payload.disabled });
    return { id, disabled: payload.disabled };
}
```

**API Client — `packages/frontend/@n8n/rest-api-client/src/api/users.ts`**

```typescript
export async function toggleUserDisabled(context, id, disabled) {
    return await makeRestApiRequest(context, 'PATCH', `/users/${id}/disabled`, { disabled });
}
```

**Store — `packages/frontend/editor-ui/src/features/settings/users/users.store.ts`**

```typescript
const toggleUserDisabled = async (id, disabled) => {
    await usersApi.toggleUserDisabled(rootStore.restApiContext, id, disabled);
    await fetchUsers({ filter: { ids: [id] } });
};
```

**UI — `packages/frontend/editor-ui/src/features/settings/users/views/SettingsUsersView.vue`**

Dua action baru di dropdown user:
- **"Disable User"** — tampil jika user aktif dan bukan diri sendiri
- **"Enable User"** — tampil jika user sudah disabled

**i18n — `packages/frontend/@n8n/i18n/src/locales/en.json`**

```json
"settings.users.actions.disableUser": "Disable User",
"settings.users.actions.enableUser": "Enable User"
```

---

## Catatan Teknis

- `workflow:viewer` di DB di-sync otomatis saat startup — tidak butuh migration manual
- Disable User menggunakan field `disabled` yang sudah ada di `User` entity dan sudah dicek di `auth.service.ts` (user tidak bisa login jika `disabled = true`)
- `project:viewer` sudah ada lengkap di n8n (`PROJECT_VIEWER_SCOPES`) — hanya perlu license bypass
