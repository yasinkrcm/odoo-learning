# Odoo 19 Learning Project: Modules, ORM, Security, Automation, RPC & Webhooks

A hands-on project for learning Odoo development end to end. It runs Odoo 19 Community in Docker, includes two custom addons covering the full range of module-building techniques (models, views, security, automation, controllers), and Python clients that talk to Odoo over XML-RPC and JSON-RPC.

## What's inside

- **Dockerized Odoo 19 + PostgreSQL** with a mounted `addons/` folder for custom modules
- **`my_first_module`**: the main addon, covering
  - a custom model (`my.todo`) with list/form views, menu and access rules
  - model inheritance (`res.partner` extended with VIP fields)
  - relational fields (`Many2one`, a `related` field, a computed field over a relation chain)
  - `@api.onchange` (UI-only convenience) vs `@api.depends` (a real computed field)
  - a form button calling a Python method, and a `sudo()` example bypassing the caller's rights for one safe write
  - an outbound call to an external API (`requests`)
  - a wizard (`TransientModel`) bound to the list view's Actions menu
  - a QWeb PDF report bound to the form's Print menu
  - a custom security group + record rules (users see only their own todos; "Todo Manager" sees and can delete everything)
  - a Server Action (bulk "mark as done") and an Automated Action (`base.automation`, logs on every create)
  - a public JSON-RPC webhook controller for external systems to create todos without XML-RPC
- **`sale_custom`**: extends the built-in Sales module
  - new fields on `sale.order` via classical inheritance
  - view inheritance (`xpath`) on the standard quotation form and list
  - a header button updating a field through a Python method
- **`odoo_rpc.py`**: an XML-RPC client covering CRUD, domain filters, `read_group`, One2many command tuples, and calls against both the custom model and standard models (`res.partner`, `crm.lead`, `sale.order`)
- **`import_customers.py`**: an idempotent CSV → RPC import script (search-then-create-or-update, never duplicates)

## Project structure

```
odoo-project/
├── docker-compose.yml
├── addons/
│   ├── my_first_module/
│   │   ├── __init__.py
│   │   ├── __manifest__.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── todo.py
│   │   │   ├── res_partner.py
│   │   │   └── todo_wizard.py
│   │   ├── controllers/
│   │   │   ├── __init__.py
│   │   │   └── webhook.py
│   │   ├── views/
│   │   │   ├── todo_views.xml
│   │   │   ├── res_partner_views.xml
│   │   │   ├── todo_wizard_views.xml
│   │   │   ├── todo_report.xml
│   │   │   └── automation_and_server_action.xml
│   │   └── security/
│   │       ├── ir.model.access.csv
│   │       └── security_advanced.xml
│   └── sale_custom/
│       ├── __init__.py
│       ├── __manifest__.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── sale_order.py
│       └── views/
│           └── sale_order_views.xml
├── odoo_rpc.py
├── import_customers.py
├── customers.csv
├── requirements.txt
├── .env.example
└── .gitignore
```

## Getting started

### Prerequisites

- Docker and Docker Compose
- Python 3.9+ (only for the RPC/import scripts)

### 1. Start Odoo

```bash
docker compose up -d
```

Open http://localhost:8069 and create a database (use a simple lowercase name, no spaces). Note the database name, email and password — the scripts need them.

> The database credentials in `docker-compose.yml` (`odoo` / `odoo`) are development defaults, never reuse them anywhere public.

### 2. Install the custom modules

1. Enable developer mode, go to **Apps**
2. Click **Update Apps List**
3. Install **Sales** first (a dependency of `sale_custom`)
4. Install **My First Module** and **Sale Custom**

### 3. Applying code changes (important)

A module already in `installed` state needs an **upgrade** (`-u`), not an **install** (`-i`), to pick up code or view changes — running `-i` again on an already-installed module does nothing.

```bash
# apply code/XML changes to an already-installed module
docker compose exec web odoo -d <your_db> -u <module_name> \
  --db_host=db --db_user=odoo --db_password=odoo --stop-after-init

# install a module for the first time
docker compose exec web odoo -d <your_db> -i <module_name> \
  --db_host=db --db_user=odoo --db_password=odoo --stop-after-init
```

Always restart the web container afterwards:

```bash
docker compose restart web
```

### 4. Give yourself the "Todo Manager" group (needed to delete todos)

Users & Companies → Groups → *Todo Manager* → Users tab → add yourself → Save. Without this, `perm_unlink` is `0` for regular users by design (see Security below).

### 5. Run the scripts

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with your database name and credentials

python3 odoo_rpc.py
python3 import_customers.py
```

`.env` is git-ignored and must never be committed.

## Module details

### `my.todo` model

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required) | Title |
| `description` | Text | Details |
| `is_done` | Boolean | Completion flag |
| `deadline` | Date | Due date |
| `user_id` | Many2one `res.users` | Assignee (defaults to current user) |
| `partner_id` | Many2one `res.partner` | Related customer |
| `partner_is_vip` | Boolean (related) | Reads `is_vip` from the linked customer |
| `partner_country` | Char (computed, stored) | Reads through `partner_id.country_id.name` |

Key methods:
- `action_mark_done()` — sets `is_done` True, returns `True` (required for RPC — `None` can't be marshalled over XML-RPC)
- `action_log_partner_note_as_admin()` — `sudo()` example, writes to the partner regardless of the caller's own rights
- `action_notify_external()` — posts to an external HTTP endpoint via `requests`
- `_onchange_partner_id()` — `@api.onchange`, UI-only, does **not** fire over RPC
- `_compute_partner_country()` — `@api.depends`, fires everywhere including RPC, because it's a real computed field

### `res.partner` extension

Classical inheritance (`_inherit`) adds `is_vip` and `vip_notes`. The Contacts form is extended via `xpath`; `vip_notes` is only visible when `is_vip` is checked.

### `sale.order` extension (`sale_custom`)

Adds `x_priority` (Selection) and `x_internal_note` (Text) via inheritance; extends the quotation form and list via `xpath`; adds a **Set Urgent** header button.

### Wizard: bulk deadline update

`my.todo.deadline.wizard` (`TransientModel`) is bound to the todo list's Actions menu via `binding_model_id`. Select rows → Actions → *Set Deadline* → applies the chosen date to every selected todo through `active_ids` in the context.

### PDF report

Bound to the form's Print menu via `binding_model_id` + `binding_type: report`. QWeb template uses `t-foreach`, `t-field` and `t-if`/`t-else` to render title, deadline, assignee, customer and status.

### Security: group + record rules

- `access_my_todo_user`: regular users get read/write/create but **not** delete
- `access_my_todo_manager`: the "Todo Manager" group gets full access including delete
- `rule_todo_own_records`: a regular user's domain is filtered to `user_id = uid` — they only see their own todos
- `rule_todo_manager_all`: "Todo Manager" bypasses that filter and sees everything

**Load order matters**: `security_advanced.xml` (which defines the group) must be listed in the manifest **before** `ir.model.access.csv` (which references that group) — otherwise the group doesn't exist yet when the CSV is parsed.

### Server Action & Automated Action

- `server_action_todo_mark_all_done`: bound to the list, bulk-sets `is_done = True` on selected records — one line of Python (`records.write(...)`), no button/view code needed
- `server_action_log_todo_created` + `automation_todo_on_create`: in Odoo 19, `base.automation` no longer holds its own code directly — it links to one or more `ir.actions.server` records via `action_server_ids`. The trigger fires on every create (Odoo 19 normalizes `on_create` to `on_create_or_write` internally)
- `log(message)` inside server-action/automation code writes to **`ir.logging`** (Settings → Technical → Logging), not to the container's stdout — check there, or query `env['ir.logging'].search(...)`, not `docker compose logs`

### Webhook controller (JSON-RPC)

`POST /my_first_module/webhook/todo` lets an external system create a todo without XML-RPC:

```bash
curl -X POST http://localhost:8069/my_first_module/webhook/todo \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "call", "params": {"name": "Webhook todo", "api_key": "change-me-secret"}}'
```

`type='jsonrpc'` (the Odoo 19 name; `type='json'` still works but is deprecated) makes Odoo handle the JSON-RPC envelope automatically. `auth='public'` means no login is required — the minimal `api_key` check in the code is a bare-minimum guard, not real security; a production webhook needs a proper secret/signature check. Uses `sudo()` since the public/anonymous user has no create rights on `my.todo`.

## XML-RPC usage

Every call goes through `execute_kw`:

```python
models.execute_kw(db, uid, password, model, method, args, kwargs)
```

```python
# CRUD on the custom model
todo_id = call('my.todo', 'create', [{'name': 'Created via RPC'}])
call('my.todo', 'search_read', [[['is_done', '=', False]]], {'fields': ['name', 'deadline']})
call('my.todo', 'write', [[todo_id], {'is_done': True}])
call('my.todo', 'action_mark_done', [[todo_id]])
call('my.todo', 'unlink', [[todo_id]])  # requires the "Todo Manager" group

# Many2one: write with an id, read back as [id, display_name]
partner_id = call('res.partner', 'create', [{'name': 'Test Customer', 'is_vip': True}])
lead_id = call('crm.lead', 'create', [{'name': 'New opportunity', 'partner_id': partner_id}])

# One2many: command tuples, e.g. (0, 0, values) to create a new line
order_id = call('sale.order', 'create', [{
    'partner_id': partner_id,
    'order_line': [(0, 0, {'product_id': product_id, 'product_uom_qty': 3})],
}])
call('sale.order', 'action_confirm', [[order_id]])

# read_group: aggregate server-side instead of pulling all rows
call('my.todo', 'read_group', [[], ['is_done'], ['is_done']])
```

Command tuple reference for One2many/Many2many: `(0, 0, values)` create, `(1, id, values)` update, `(2, id, 0)` delete, `(3, id, 0)` unlink, `(4, id, 0)` link existing, `(6, 0, [ids])` replace all links.

## CSV import (idempotent)

`import_customers.py` searches by email before writing: existing customer → `write`, otherwise `create`. Running it twice never creates duplicates — verified by running it back-to-back and confirming the second pass reports only `updated`, not `created`.

## Notes on Odoo 19

- List views use `<list>`. `<tree>` is no longer valid and causes a `ParseError` on install.
- Methods called over XML-RPC must not return `None`. Return `True` instead.
- Methods starting with `_` are private and cannot be called through RPC.
- A module already `installed` needs `-u` (upgrade), not `-i` (install), to pick up changes.
- `res.groups` no longer has a `category_id` field in this version — omit it, the group still works, just without a category grouping in the Users form.
- `base.automation` no longer holds inline code — link to an `ir.actions.server` via `action_server_ids`.
- `@route(type='json')` is deprecated in favor of `type='jsonrpc'`.
- The `version` key in `docker-compose.yml` is obsolete and can be removed.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Database creation error: 'NoneType' object has no attribute 'uid'` | Restart the web container; use a simple database name |
| `Invalid view type: 'tree'` | Replace `<tree>` with `<list>` |
| `column ... does not exist` | Code loaded but not upgraded; run the `-u` command |
| New field/view doesn't appear even though **Installed** | Only ever *installed*, never *upgraded* after the change — run `-u`, restart, hard-refresh |
| `No matching record found for external id 'group_xxx'` | Manifest `data` order is wrong — the file defining the group must load *before* the file referencing it |
| `Invalid field 'category_id' in 'res.groups'` | Remove that field from the group definition (removed in Odoo 19) |
| `Invalid field 'state' in 'base.automation'` | Odoo 19 automations link to server actions via `action_server_ids` instead of holding code directly |
| Automation seems to do nothing | Check `ir.logging` (or query `env['ir.logging']` in `odoo shell`), not `docker compose logs` — `log()` writes to the database |
| `You are not allowed to delete ... records` | Expected — only the "Todo Manager" group can delete todos; add yourself to that group |
| Todos "disappear" for a regular user | Expected — the record rule filters to `user_id = uid`; use `env['my.todo'].sudo().search_count([])` in `odoo shell` to confirm records still exist |
| `cannot marshal None` over RPC | Make the called method `return True` |
| Fetchmail errors in logs | Harmless if a personal mailbox is connected as an Incoming Mail Server; remove it under Settings → Technical → Incoming Mail Servers if not needed |

## Roadmap

- [ ] Automated tests (`TransactionCase`)
- [ ] Tie the pieces into one end-to-end flow: webhook → automation → wizard → server action → PDF report
- [ ] Multi-company support (`company_id` + company-scoped record rules)

## Author

Yasin Karacam: [GitHub](https://github.com/yasinkrcm) · [Portfolio](https://yasinkaracam.com)