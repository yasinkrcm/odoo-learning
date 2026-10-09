# Odoo 19 Custom Addons & Architecture: Modules, ORM, Security, POS Sync, Progress Billing & RPC

A production-ready, hands-on repository showcasing modern **Odoo 19 Community** development end-to-end. It features containerized Odoo 19 + PostgreSQL, four fully featured custom modules covering real-world business flows (construction progress billing, retail POS stock sync, sales customization, and full-stack ORM patterns), external Python XML-RPC clients, and JSON-RPC webhooks.

---

## 📦 What's Inside

| Module / Tool | Category | Core Concepts & Capabilities | Dependencies |
|---|---|---|---|
| **`my_first_module`** | Core / Productivity | Custom models (`my.todo`), `TransientModel` wizards, relational fields (`Many2one`, `related`, stored computed), `@api.depends` vs `@api.onchange`, `sudo()` elevated writes, external HTTP requests, QWeb PDF reports, multi-tier security groups, record rules, server actions, automated actions (`base.automation`), and public JSON-RPC webhook. | `base`, `web`, `contacts` |
| **`sale_custom`** | Sales | Classical model inheritance (`sale.order`), view inheritance via `<xpath>`, custom priority & internal notes, header action buttons. | `sale` |
| **`buksu_hakedis`** | Project & Accounting | Construction / traffic site subcontractor progress billing (*Hakediş*). Multi-team progress tracking (`buksu.hakedis.donem`, `buksu.hakedis.satir`, `buksu.ekip`), strict forward-only status workflow (`taslak` → `onaylandi` → `odendi`), dynamic line calculations (metraj, unit price, deductions), vendor bill creation (`account.move`), sequence auto-numbering, `project.project` smart button integration, and official QWeb PDF progress reports. | `base`, `project`, `web`, `account` |
| **`nisa_pos_sync`** | Inventory & POS | Bidirectional product and stock synchronization with external POS systems. Product template extension (`external_pos_id`, `nisa_stock_qty`), HMAC-secured atomic webhook deductions with savepoint concurrency protection, audit sync log model (`nisa.sync.log`), system parameters configuration, and built-in mock POS server for testing. | `product` |
| **`odoo_rpc.py`** | Integration | External XML-RPC Python client demonstrating CRUD operations, domain filters, server-side aggregation (`read_group`), One2many command tuples, and model method execution. | `xmlrpc.client`, `python-dotenv` |
| **`import_customers.py`** | ETL / Migration | Idempotent CSV import script using XML-RPC (search-before-write, upsert pattern preventing duplicate customer entries). | `csv`, `python-dotenv` |

---

## 🗂️ Project Structure

```
odoo-project/
├── docker-compose.yml              # Odoo 19 + PostgreSQL 15 environment
├── requirements.txt                # Local Python dependencies for RPC scripts
├── .env.example                    # Environment template for RPC clients
├── .gitignore                      # Git ignore rules (macOS, Python, venv, .env)
├── odoo_rpc.py                     # XML-RPC client for automated Odoo tasks
├── import_customers.py             # Idempotent CSV customer importer
├── customers.csv                   # Sample dataset for bulk import
├── README.md                       # Comprehensive repository documentation
└── addons/
    ├── my_first_module/            # Foundation module: ORM, wizards, actions & webhook
    │   ├── __init__.py
    │   ├── __manifest__.py
    │   ├── models/
    │   │   ├── __init__.py
    │   │   ├── todo.py             # my.todo model with computed fields & logic
    │   │   ├── res_partner.py      # res.partner VIP extension
    │   │   └── todo_wizard.py      # TransientModel bulk deadline wizard
    │   ├── controllers/
    │   │   ├── __init__.py
    │   │   └── webhook.py          # JSON-RPC public endpoint
    │   ├── views/
    │   │   ├── todo_views.xml
    │   │   ├── res_partner_views.xml
    │   │   ├── todo_wizard_views.xml
    │   │   ├── todo_report.xml     # QWeb PDF report definition
    │   │   └── automation_and_server_action.xml
    │   └── security/
    │       ├── ir.model.access.csv
    │       └── security_advanced.xml # Groups & record-level access rules
    │
    ├── sale_custom/                # Sales order extension
    │   ├── __init__.py
    │   ├── __manifest__.py
    │   ├── models/
    │   │   ├── __init__.py
    │   │   └── sale_order.py       # Custom fields & urgent button method
    │   └── views/
    │       └── sale_order_views.xml# XPath injections into standard views
    │
    ├── buksu_hakedis/              # Subcontractor Progress Billing (Hakediş)
    │   ├── __init__.py
    │   ├── __manifest__.py
    │   ├── data/
    │   │   └── sequence.xml        # Auto-sequence generator (HAK/YYYY/...)
    │   ├── models/
    │   │   ├── __init__.py
    │   │   ├── buksu_hakedis.py    # Billing periods & line calculation logic
    │   │   ├── buksu_ekip.py       # Field subcontractor teams
    │   │   └── project_project.py  # Project extension with smart stat buttons
    │   ├── views/
    │   │   ├── buksu_hakedis_views.xml
    │   │   ├── buksu_ekip_views.xml
    │   │   └── project_views.xml
    │   ├── report/
    │   │   └── buksu_hakedis_report.xml # Formal progress billing printout
    │   └── security/
    │       ├── ir.model.access.csv
    │       └── security.xml
    │
    └── nisa_pos_sync/              # External POS & Stock Synchronization
        ├── __init__.py
        ├── __manifest__.py
        ├── data/
        │   └── ir_config_parameter.xml # API URLs and authentication keys
        ├── models/
        │   ├── __init__.py
        │   ├── product_template.py # POS attributes & outbound push methods
        │   ├── product_product.py  # Variant helper bindings
        │   └── nisa_sync_log.py    # Audit logging for sync events
        ├── controllers/
        │   ├── __init__.py
        │   ├── webhook.py          # Inbound sale webhook with atomic stock drop
        │   └── mock_pos.py         # Mock server for sandbox POS testing
        ├── views/
        │   ├── product_template_views.xml
        │   └── nisa_sync_log_views.xml
        └── security/
            └── ir.model.access.csv
```

---

## 🚀 Getting Started

### Prerequisites

- [Docker & Docker Compose](https://www.docker.com/)
- Python 3.9+ (required only if running the external RPC/import scripts)

### 1. Launch the Stack

```bash
docker compose up -d
```

Access the Odoo web client at [http://localhost:8069](http://localhost:8069).
Create a database (e.g. `odoo19_dev`). Keep the database name, admin email, and password handy for `.env`.

> **Note:** The database credentials in `docker-compose.yml` (`odoo` / `odoo`) are local development defaults. Do not use them in production environments.

### 2. Install Dependencies & Custom Modules

1. Log into Odoo and activate **Developer Mode** (*Settings* → scroll down → *Activate the developer mode*).
2. Go to **Apps** and click **Update Apps List** in the top navigation bar.
3. Install standard base dependencies first:
   - **Sales** (`sale` - required for `sale_custom`)
   - **Project** (`project` - required for `buksu_hakedis`)
   - **Accounting / Invoicing** (`account` - required for `buksu_hakedis`)
4. Install the custom modules:
   - **My First Module** (`my_first_module`)
   - **Sale Custom** (`sale_custom`)
   - **Buksu Hakediş Takibi** (`buksu_hakedis`)
   - **NISA POS Sync** (`nisa_pos_sync`)

---

## ⚡ Applying Code Changes (Upgrade Workflow)

In Odoo, an installed module does **not** reload Python or XML definitions simply by running `-i`. To reload changes, execute an upgrade (`-u`):

```bash
# Upgrade an installed module after modifying code or XML:
docker compose exec web odoo -d <your_db> -u <module_name> \
  --db_host=db --db_user=odoo --db_password=odoo --stop-after-init

# Example: upgrading buksu_hakedis
docker compose exec web odoo -d odoo19_dev -u buksu_hakedis \
  --db_host=db --db_user=odoo --db_password=odoo --stop-after-init
```

Restart the web container after upgrading:

```bash
docker compose restart web
```

---

## 🛠️ Modules Breakdown & Technical Architecture

### 1. `buksu_hakedis` (Subcontractor Progress Billing)

Designed for construction, utility, and infrastructure contractors managing field subcontractor teams (*taşeron ekipler*).

- **Billing Periods (`buksu.hakedis.donem`):**
  - Unique auto-incrementing reference number via `ir.sequence` (e.g. `HAK/2026/0001`).
  - Strict forward-only state workflow: `Taslak (Draft)` → `Onaylandı (Approved)` → `Ödendi (Paid)`. Status rollbacks are prevented at the model level via `write()`.
  - Stored computed totals: `brut_toplam` (gross total), `kesinti_tutari` (deductions), `net_tutar` (net payable).
  - Vendor bill integration: direct linking with `account.move` (`in_invoice`) to track payment states automatically.
- **Line Items (`buksu.hakedis.satir`):**
  - Per-item quantity (*metraj*), unit (*birim*), unit price (*birim fiyat*), and deduction percentages.
- **Subcontractor Teams (`buksu.ekip`):**
  - Manages crew contacts, foremen, and linked partner accounts (`res.partner`).
- **Project Integration (`project.project`):**
  - Injects smart stat button and dedicated notebook tab into the native Project form view, listing all billing periods and aggregate net totals.
- **Formal QWeb PDF Report:**
  - Standardized printout layout containing project details, period breakdown, signature blocks, and itemized calculations.

---

### 2. `nisa_pos_sync` (External POS & Inventory Integration)

Handles synchronization between Odoo Inventory/Product catalog and external Point-of-Sale (POS) systems.

- **Product Catalog Enhancements (`product.template`):**
  - `external_pos_id`: Unique identifier assigned by the POS system.
  - `nisa_stock_qty`: Synchronized stock balance.
  - `nisa_last_sync`: Timestamp recording last successful sync event.
  - Outbound push methods (`_nisa_push_one`, `action_nisa_push_pos`) with timeout handling.
- **Inbound Webhook (`/nisa_pos_sync/webhook/sale`):**
  - JSON-RPC public endpoint handling external retail sale events.
  - Security validation: verifies `X-API-Key` using constant-time string comparison (`hmac.compare_digest`) against `nisa_pos_sync.webhook_key`.
  - **Atomic Stock Deduction:** Uses database row savepoints and explicit SQL (`UPDATE product_template SET nisa_stock_qty = nisa_stock_qty - %s`) to prevent race conditions during high-volume sales.
- **Audit Logging (`nisa.sync.log`):**
  - Comprehensive history of all sync transactions, payload bodies, error logs, and timestamps.
- **Mock POS Test Sandbox (`/nisa_pos_sync/mock/products`):**
  - A mock HTTP endpoint simulating external POS responses during local development and testing.

---

### 3. `my_first_module` (ORM, Views, Wizards, Security & Webhooks)

A comprehensive reference implementation covering the Odoo framework fundamentals.

- **`my.todo` Model:**
  - Relational mapping: `Many2one` (`res.users`, `res.partner`), `related` fields, and stored computed fields chaining relational paths (`_compute_partner_country`).
  - Distinction between `@api.onchange` (UI-only dynamic autofill) and `@api.depends` (database-level computed trigger).
  - Privileged execution: `sudo()` method demonstrating safe privilege escalation.
  - Outbound REST trigger posting updates to third-party endpoints using `requests`.
- **TransientModel Wizard (`my.todo.deadline.wizard`):**
  - Multi-record bulk action bound to list view Actions menu; updates deadlines for all `active_ids` in context.
- **Security & Record Rules:**
  - Two-tier security structure: standard user vs. **Todo Manager**.
  - Row-level record rules: regular users can view only their own records (`user_id = uid`), while managers access and delete all records.
- **Server Action & Automation:**
  - Server Action bulk-marking records as done.
  - `base.automation` triggering a linked `ir.actions.server` on record creation, logging to `ir.logging`.
- **Public JSON-RPC Webhook (`/my_first_module/webhook/todo`):**
  - Allows external services to create tasks via authenticated POST requests.

---

### 4. `sale_custom` (Sales Order Customization)

Demonstrates clean, modular extension of standard Odoo core applications without modifying core code.

- Adds `x_priority` (Selection) and `x_internal_note` (Text) to `sale.order`.
- Leverages `<xpath>` syntax to inject custom widgets and buttons directly into standard quotation form and list views.
- Implements a **Set Urgent** header button that programmatically transitions priority states.

---

## 📡 RPC Scripts & Webhooks

### 1. Setting Up Local Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your local Odoo credentials and database name
```

### 2. XML-RPC Operations (`odoo_rpc.py`)

Run the script to execute CRUD queries, domain filtering, and aggregated lookups over XML-RPC:

```bash
python3 odoo_rpc.py
```

Code highlights:

```python
# CRUD on custom model
todo_id = call('my.todo', 'create', [{'name': 'Created via RPC'}])
call('my.todo', 'search_read', [[['is_done', '=', False]]], {'fields': ['name', 'deadline']})
call('my.todo', 'write', [[todo_id], {'is_done': True}])
call('my.todo', 'action_mark_done', [[todo_id]])

# Server-side grouping (read_group)
call('my.todo', 'read_group', [[], ['is_done'], ['is_done']])

# Relational command tuples on standard sales orders
order_id = call('sale.order', 'create', [{
    'partner_id': partner_id,
    'order_line': [(0, 0, {'product_id': product_id, 'product_uom_qty': 3})],
}])
```

*Command tuple cheatsheet for One2many / Many2many:*
- `(0, 0, values)` — Create and link new record
- `(1, id, values)` — Update linked record
- `(2, id, 0)` — Remove and delete linked record
- `(3, id, 0)` — Unlink record (do not delete)
- `(4, id, 0)` — Link existing record
- `(6, 0, [ids])` — Replace all links with specified IDs

### 3. Idempotent Customer Import (`import_customers.py`)

Reads from `customers.csv` and uses search-before-write logic to ensure repeated runs never create duplicate contacts:

```bash
python3 import_customers.py
```

### 4. Calling Webhooks (cURL)

**Todo Webhook:**
```bash
curl -X POST http://localhost:8069/my_first_module/webhook/todo \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "name": "Urgent Inspection Task",
      "api_key": "change-me-secret"
    }
  }'
```

**POS Sale Deduction Webhook:**
```bash
curl -X POST http://localhost:8069/nisa_pos_sync/webhook/sale \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-webhook-secret-key-123" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "lines": [
        {"barcode": "8690000000001", "qty": 2}
      ]
    }
  }'
```

---

## 📌 Critical Odoo 19 Development Notes

- **`<list>` replaces `<tree>`:** In Odoo 19, list views must be declared using `<list>`. Using `<tree>` produces a fatal `ParseError` on module installation.
- **RPC Return Values:** Methods invoked through XML-RPC must return a serializable value (`True`, dictionary, list, or scalar). Returning `None` raises a marshalling exception.
- **Private Methods:** Methods prefixed with `_` are strictly private to the ORM and cannot be called externally via RPC.
- **`res.groups` Structure:** The `category_id` field has been removed from `res.groups` in Odoo 19. Define groups without `category_id`.
- **`base.automation` Architecture:** Automated actions no longer store inline Python code. They must be linked to an `ir.actions.server` record via `action_server_ids`.
- **Logging Destination:** `log(...)` statements inside automated actions write to `ir.logging` in the database (*Settings* → *Technical* → *Logging*), not to the Docker container console output.
- **Controller Route Decorators:** Use `@http.route(type='jsonrpc')`. The previous `type='json'` is deprecated.

---

## 🔍 Troubleshooting Guide

| Issue / Error | Root Cause | Solution |
|---|---|---|
| `Database creation error: 'NoneType' object has no attribute 'uid'` | Temporary connection race on fresh database initialization. | Restart the web container (`docker compose restart web`) and use a simple lowercase db name. |
| `Invalid view type: 'tree'` | Deprecated XML tag used in Odoo 19 view definition. | Replace `<tree>` with `<list>` in your view XML. |
| `column ... does not exist` | Model Python code updated with new fields, but database schema not updated. | Run the upgrade command (`-u <module_name>`) and restart the container. |
| Changes in XML/Python do not appear in UI | Module is in `installed` state and does not auto-reload on container restart. | Perform an upgrade (`-u <module_name>`) and do a browser hard refresh (`Cmd+Shift+R` / `Ctrl+F5`). |
| `No matching record found for external id 'group_xxx'` | Manifest `data` list order is incorrect. | Ensure the file declaring the security group (`security.xml`) appears **before** `ir.model.access.csv`. |
| `You are not allowed to delete ... records` | User does not belong to the manager security group (`perm_unlink = 0`). | In Odoo, navigate to *Users & Companies* → *Groups*, select the manager group, and assign your user. |
| Records invisible to standard user | Row-level record rule filters records to `user_id = uid`. | Expected security behavior. Switch to a manager account or inspect with `sudo()` in `odoo shell`. |
| `cannot marshal None` | Method called via XML-RPC finished without returning a value. | Ensure the method explicitly finishes with `return True`. |

---

## 👨‍💻 Author

**Yasin Karaçam**
- GitHub: [@yasinkrcm](https://github.com/yasinkrcm)
- Portfolio: [yasinkaracam.com](https://yasinkaracam.com)