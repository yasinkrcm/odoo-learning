# Odoo 19 Learning Project: Custom Modules + XML-RPC Client

A hands-on project for learning Odoo development. It runs Odoo 19 Community in Docker, includes two custom addons demonstrating the core building blocks of Odoo module development, and a Python client that talks to Odoo over XML-RPC.

## What's inside

- **Dockerized Odoo 19 + PostgreSQL** with a mounted `addons/` folder for custom modules
- **`my_first_module`**: a standalone addon featuring
  - a new model (`my.todo`) with list and form views, menu and access rules
  - model inheritance (`res.partner` extended with VIP fields)
  - relational fields (`Many2one` to users and partners, plus a related field)
  - a form button that calls a Python method
- **`sale_custom`**: an addon that extends the built-in Sales module
  - new fields on `sale.order` (`x_priority`, `x_internal_note`) via classical inheritance
  - view inheritance (`xpath`) on the standard quotation form and list views
  - a header button that updates a field through a Python method
- **`odoo_rpc.py`**: an XML-RPC client demonstrating CRUD, domain filters, command tuples for One2many/Many2many, and calls against both a custom model and standard models (`res.partner`, `crm.lead`, `sale.order`)

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
│   │   │   └── res_partner.py
│   │   ├── views/
│   │   │   ├── todo_views.xml
│   │   │   └── res_partner_views.xml
│   │   └── security/
│   │       └── ir.model.access.csv
│   └── sale_custom/
│       ├── __init__.py
│       ├── __manifest__.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── sale_order.py
│       └── views/
│           └── sale_order_views.xml
├── odoo_rpc.py
├── requirements.txt
├── .env.example
└── .gitignore
```

## Getting started

### Prerequisites

- Docker and Docker Compose
- Python 3.9+ (only for the RPC client)

### 1. Start Odoo

```bash
docker compose up -d
```

Open http://localhost:8069 and create a database (use a simple lowercase name such as `odoo_db`, without spaces). Note the master password, database name, email and password you choose. The RPC client needs them.

> The database credentials in `docker-compose.yml` (`odoo` / `odoo`) are development defaults. Do not reuse them anywhere public.

### 2. Install the custom modules

1. In Odoo, enable developer mode and go to **Apps**
2. Click **Update Apps List**
3. Install **Sales** first (a dependency of `sale_custom`)
4. Search for **My First Module** and **Sale Custom**, install both

### 3. Applying code changes (important)

Odoo tracks each module's install state. If a module already shows as `installed`, running an *install* command again does nothing — code and XML changes only apply on an *upgrade*. This distinction cost real debugging time in this project (see Troubleshooting), so it's worth internalizing:

```bash
# apply code/XML changes to an already-installed module
docker compose exec web odoo -d <your_db> -u <module_name> \
  --db_host=db --db_user=odoo --db_password=odoo --stop-after-init

# install a module for the first time
docker compose exec web odoo -d <your_db> -i <module_name> \
  --db_host=db --db_user=odoo --db_password=odoo --stop-after-init
```

Always restart the web container afterwards so the running server picks up the new registry:

```bash
docker compose restart web
```

Python-only changes with no new fields or XML can sometimes get by with just a restart, but running the explicit `-u` command is the reliable path.

### 4. Run the XML-RPC client

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with your database name and credentials

python3 odoo_rpc.py
```

`.env` is git-ignored and must never be committed.

## Module details

### `my.todo` model (`my_first_module`)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required) | Title |
| `description` | Text | Details |
| `is_done` | Boolean | Completion flag |
| `deadline` | Date | Due date |
| `user_id` | Many2one `res.users` | Assignee |
| `partner_id` | Many2one `res.partner` | Related customer |
| `partner_is_vip` | Boolean (related) | Reads `is_vip` from the linked customer |

`action_mark_done()` sets `is_done` to `True` and returns `True`. It is exposed as a **Mark as Done** button on the form view and can also be called over RPC.

### `res.partner` extension (`my_first_module`)

Classical inheritance (`_inherit = 'res.partner'`) adds `is_vip` and `vip_notes`. The Contacts form is extended through an `xpath` view inheritance, and `vip_notes` is only visible when `is_vip` is checked.

### `sale.order` extension (`sale_custom`)

Classical inheritance adds `x_priority` (Selection: normal/high/urgent) and `x_internal_note` (Text) to the standard Sales Order model. The quotation form is extended via `xpath` to show the new field next to the customer and add a **Set Urgent** button in the header; the list view shows priority next to the total.

## XML-RPC usage

Every call goes through `execute_kw`:

```python
models.execute_kw(db, uid, password, model, method, args, kwargs)
```

Custom model examples:

```python
todo_id = call('my.todo', 'create', [{'name': 'Created via RPC'}])
call('my.todo', 'search_read', [[['is_done', '=', False]]], {'fields': ['name', 'deadline']})
call('my.todo', 'write', [[todo_id], {'is_done': True}])
call('my.todo', 'action_mark_done', [[todo_id]])
call('my.todo', 'unlink', [[todo_id]])
```

Standard model examples (Many2one read vs. write asymmetry, and One2many command tuples):

```python
# Many2one: write with an id, read back as [id, display_name]
partner_id = call('res.partner', 'create', [{'name': 'Test Customer', 'is_vip': True}])
lead_id = call('crm.lead', 'create', [{'name': 'New opportunity', 'partner_id': partner_id}])

# One2many: command tuples are required, e.g. (0, 0, values) to create a new line
order_id = call('sale.order', 'create', [{
    'partner_id': partner_id,
    'order_line': [(0, 0, {'product_id': product_id, 'product_uom_qty': 3})],
}])
call('sale.order', 'action_confirm', [[order_id]])
```

Command tuple reference for One2many/Many2many fields: `(0, 0, values)` create, `(1, id, values)` update, `(2, id, 0)` delete, `(3, id, 0)` unlink, `(4, id, 0)` link existing, `(6, 0, [ids])` replace all links.

## Notes on Odoo 19

- List views use the `<list>` tag. `<tree>` is no longer valid and causes a `ParseError` on install.
- Methods called over XML-RPC must not return `None` (XML-RPC cannot marshal it). Return `True` instead.
- Methods whose names start with `_` are private and cannot be called through RPC.
- A module already in `installed` state needs `-u` (upgrade), not `-i` (install), to pick up code or view changes.
- The `version` key in `docker-compose.yml` is obsolete and can be removed.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Database creation error: 'NoneType' object has no attribute 'uid'` | Restart the web container; use a simple database name |
| `Invalid view type: 'tree'` | Replace `<tree>` with `<list>` (Odoo 19) |
| `column res_partner.is_vip does not exist` | The module code is loaded but not upgraded; run the CLI upgrade command above |
| New field/view doesn't appear even though the module shows **Installed** | The module was only ever *installed*, never *upgraded*, after the change. Run the `-u` command, then restart and hard-refresh the browser |
| `Connection to the database failed` when running `odoo` via `docker compose exec` | Pass `--db_host=db --db_user=odoo --db_password=odoo` |
| `cannot marshal None` over RPC | Make the called method `return True` |
| "Odoo is currently processing a scheduled action" | Wait a moment or restart the web container; this also blocks `button_immediate_install()` from the Odoo shell while a cron is running |
| Fetchmail errors in logs (`No possible route found for incoming message...`) | Harmless if a personal mailbox is connected as an Incoming Mail Server; remove it under Settings → Technical → Incoming Mail Servers if not needed |

## Roadmap

- [ ] Add a wizard (`TransientModel`) for bulk actions
- [ ] Add a QWeb PDF report
- [ ] Import external CSV data into Odoo through RPC
- [ ] Record rules so users only see their own todos

## Author

Yasin Karacam: [GitHub](https://github.com/yasinkrcm) · [Portfolio](https://yasinkaracam.com)