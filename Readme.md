# Odoo 19 Learning Project: Custom Module + XML-RPC Client

A hands-on project for learning Odoo development. It runs Odoo 19 Community in Docker, includes a custom addon (`my_first_module`) that demonstrates the core building blocks of Odoo module development, and a small Python client that talks to Odoo over XML-RPC.

## What's inside

- **Dockerized Odoo 19 + PostgreSQL** with a mounted `addons/` folder for custom modules
- **`my_first_module`**: a custom addon featuring
  - a new model (`my.todo`) with list and form views, menu and access rules
  - model inheritance (`res.partner` extended with VIP fields)
  - relational fields (`Many2one` to users and partners, plus a related field)
  - a form button that calls a Python method
- **`odoo_rpc.py`**: an XML-RPC client demonstrating create / read / update / call-method / delete, configured through environment variables

## Project structure

```
odoo-project/
├── docker-compose.yml
├── addons/
│   └── my_first_module/
│       ├── __init__.py
│       ├── __manifest__.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── todo.py
│       │   └── res_partner.py
│       ├── views/
│       │   ├── todo_views.xml
│       │   └── res_partner_views.xml
│       └── security/
│           └── ir.model.access.csv
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

### 2. Install the custom module

1. In Odoo, enable developer mode and go to **Apps**
2. Click **Update Apps List**
3. Search for **My First Module** and click **Install**
4. A new **My Todos** menu appears in the main menu

To apply code changes to an already installed module, restart the web container and upgrade the module from the CLI:

```bash
docker compose restart web
docker compose exec web odoo -d <your_db> -u my_first_module \
  --db_host=db --db_user=odoo --db_password=odoo --stop-after-init
docker compose restart web
```

Python-only changes (no new fields or XML) only need `docker compose restart web`.

### 3. Run the XML-RPC client

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

### `my.todo` model

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required) | Title |
| `description` | Text | Details |
| `is_done` | Boolean | Completion flag |
| `deadline` | Date | Due date |
| `user_id` | Many2one `res.users` | Assignee |
| `partner_id` | Many2one `res.partner` | Related customer |
| `partner_is_vip` | Boolean (related) | Reads `is_vip` from the linked customer |

`action_mark_done()` sets `is_done` to `True`. It is exposed as a **Mark as Done** button on the form view and can also be called over RPC.

### `res.partner` extension

Classical inheritance (`_inherit = 'res.partner'`) adds `is_vip` and `vip_notes`. The Contacts form is extended through an `xpath` view inheritance, and `vip_notes` is only visible when `is_vip` is checked.

## XML-RPC usage

Every call goes through `execute_kw`:

```python
models.execute_kw(db, uid, password, model, method, args, kwargs)
```

Examples (from `odoo_rpc.py`):

```python
# Create
todo_id = call('my.todo', 'create', [{'name': 'Created via RPC'}])

# Read with a domain filter
call('my.todo', 'search_read', [[['is_done', '=', False]]],
     {'fields': ['name', 'deadline'], 'limit': 10})

# Update
call('my.todo', 'write', [[todo_id], {'is_done': True}])

# Call a model method
call('my.todo', 'action_mark_done', [[todo_id]])

# Delete
call('my.todo', 'unlink', [[todo_id]])
```

## Notes on Odoo 19

- List views use the `<list>` tag. `<tree>` is no longer valid and causes a `ParseError` on install.
- Methods called over XML-RPC must not return `None` (XML-RPC cannot marshal it). Return `True` instead.
- Methods whose names start with `_` are private and cannot be called through RPC.
- The `version` key in `docker-compose.yml` is obsolete and can be removed.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Database creation error: 'NoneType' object has no attribute 'uid'` | Restart the web container; use a simple database name |
| `Invalid view type: 'tree'` | Replace `<tree>` with `<list>` (Odoo 19) |
| `column res_partner.is_vip does not exist` | The module code is loaded but not upgraded; run the CLI upgrade command above |
| `Connection to the database failed` when running `odoo` via `docker compose exec` | Pass `--db_host=db --db_user=odoo --db_password=odoo` |
| `cannot marshal None` over RPC | Make the called method `return True` |
| "Odoo is currently processing a scheduled action" | Wait a moment or restart the web container |

## Roadmap

- [ ] Extend `sale.order` with custom fields and buttons
- [ ] Add a wizard (`TransientModel`) for bulk actions
- [ ] Add a QWeb PDF report
- [ ] Import external CSV data into Odoo through RPC
- [ ] Record rules so users only see their own todos

## Author

Yasin Karacam: [GitHub](https://github.com/yasinkrcm) · [Portfolio](https://yasinkaracam.com)