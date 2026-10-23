#!/usr/bin/env python3
"""Generate and validate a minimal Odoo 19 module from a JSON spec.

Usage:
    python tools/odoo_scaffold.py tools/specs/library_loans.json
    python tools/odoo_scaffold.py tools/specs/library_loans.json --install
"""
import argparse
import json
import keyword
import re
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parent.parent
ADDONS = ROOT / 'addons'

MODULE_RE = re.compile(r'^[a-z][a-z0-9_]{2,40}$')
MODEL_RE = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$')
FIELD_RE = re.compile(r'^[a-z][a-z0-9_]*$')
TYPES = {
    'Char', 'Text', 'Integer', 'Float', 'Boolean',
    'Date', 'Datetime', 'Html', 'Selection', 'Many2one', 'Many2many',
}
RELATIONAL = {'Many2one', 'Many2many'}
NO_DEFAULT = {'Date', 'Datetime', 'Html'} | RELATIONAL
RESERVED = {'id', 'create_date', 'create_uid', 'write_date', 'write_uid', 'display_name'}


# ---------------------------------------------------------------- validation
def lint(spec):
    errors = []
    if not isinstance(spec, dict):
        return ['spec must be a JSON object']
    module = spec.get('module', '')
    if not MODULE_RE.match(module):
        errors.append(f'invalid module name {module!r} (use lowercase letters, digits, underscore)')
    if not spec.get('name'):
        errors.append('missing "name"')
    models = spec.get('models')
    if not isinstance(models, list) or not models:
        errors.append('"models" must be a non-empty list')
        return errors

    seen_models = set()
    for m in models:
        mn = m.get('name', '')
        if not MODEL_RE.match(mn):
            errors.append(f'invalid model name {mn!r} (expected something like "library.loan")')
            continue
        if mn in seen_models:
            errors.append(f'duplicate model {mn}')
        seen_models.add(mn)
        fields = m.get('fields')
        if not isinstance(fields, list) or not fields:
            errors.append(f'{mn}: "fields" must be a non-empty list')
            continue
        names = set()
        has_name_char = False
        for f in fields:
            fn = f.get('name', '')
            ft = f.get('type')
            where = f'{mn}.{fn}'
            if not FIELD_RE.match(fn) or keyword.iskeyword(fn):
                errors.append(f'{where}: invalid field name')
                continue
            if fn in RESERVED:
                errors.append(f'{where}: reserved field name')
            if fn in names:
                errors.append(f'{where}: duplicate field')
            names.add(fn)
            if ft not in TYPES:
                errors.append(f'{where}: unsupported type {ft!r} (allowed: {sorted(TYPES)})')
                continue
            if fn == 'name' and ft == 'Char':
                has_name_char = True
            if ft in RELATIONAL and not MODEL_RE.match(str(f.get('comodel', ''))):
                errors.append(f'{where}: {ft} needs a valid "comodel"')
            if ft == 'Selection':
                sel = f.get('selection')
                ok = (
                    isinstance(sel, list) and sel
                    and all(isinstance(x, list) and len(x) == 2 and all(isinstance(i, str) for i in x) for x in sel)
                )
                if not ok:
                    errors.append(f'{where}: "selection" must be a list of [key, label] pairs')
                elif 'default' in f and f['default'] not in [x[0] for x in sel]:
                    errors.append(f'{where}: default {f["default"]!r} is not one of the selection keys')
            if 'default' in f and ft in NO_DEFAULT:
                errors.append(f'{where}: "default" is not supported for {ft}')
        if not has_name_char:
            errors.append(f'{mn}: needs a Char field called "name" (used as the record title)')
    return errors


# ---------------------------------------------------------------- rendering
def label(f):
    return f.get('string') or re.sub(r'_ids?$', '', f['name']).replace('_', ' ').title()


def render_field(f, chatter):
    t = f['type']
    args = []
    if t == 'Selection':
        args.append(repr([tuple(x) for x in f['selection']]))
    elif t in RELATIONAL:
        args.append(repr(f['comodel']))
    args.append(f'string={label(f)!r}')
    if f.get('required'):
        args.append('required=True')
    if 'default' in f:
        args.append(f'default={f["default"]!r}')
    if f.get('tracking', chatter and t not in ('Text', 'Html')):
        args.append('tracking=True')
    return f'    {f["name"]} = fields.{t}({", ".join(args)})'


def render_model_py(m):
    chatter = m.get('chatter', False)
    cls = ''.join(p.capitalize() for p in m['name'].split('.'))
    desc = m.get('description') or m['name']
    lines = [
        'from odoo import fields, models',
        '',
        '',
        f'class {cls}(models.Model):',
        f'    _name = {m["name"]!r}',
        f'    _description = {desc!r}',
    ]
    if chatter:
        lines.append("    _inherit = ['mail.thread', 'mail.activity.mixin']")
    lines.append('')
    lines += [render_field(f, chatter) for f in m['fields']]
    return '\n'.join(lines) + '\n'


def render_acl(spec):
    rows = ['id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink']
    for m in spec['models']:
        mu = m['name'].replace('.', '_')
        unlink = 1 if m.get('allow_delete') else 0
        rows.append(f'access_{mu}_user,{m["name"]}.user,model_{mu},base.group_user,1,1,1,{unlink}')
    return '\n'.join(rows) + '\n'


def render_views(m):
    mu = m['name'].replace('.', '_')
    model = m['name']
    desc = m.get('description') or model
    chatter = m.get('chatter', False)
    flds = m['fields']
    has_state = any(f['name'] == 'state' and f['type'] == 'Selection' for f in flds)
    short = [f for f in flds if f['type'] not in ('Text', 'Html')]
    long_ = [f for f in flds if f['type'] in ('Text', 'Html')]
    body = [f for f in short if not (has_state and f['name'] == 'state')]
    half = (len(body) + 1) // 2

    def fl(fs, ind):
        return '\n'.join(f'{ind}<field name="{f["name"]}"/>' for f in fs)

    header = ''
    if has_state:
        header = '                <header>\n                    <field name="state" widget="statusbar"/>\n                </header>\n'
    notebook = ''
    if long_:
        pages = '\n'.join(
            f'                        <page string={quoteattr(label(f))}>\n'
            f'                            <field name="{f["name"]}"/>\n'
            f'                        </page>'
            for f in long_
        )
        notebook = f'                    <notebook>\n{pages}\n                    </notebook>\n'
    chatter_xml = '                <chatter/>\n' if chatter else ''

    search_fields = fl(short[:3], '                ')
    groupbys = [f for f in flds if f['type'] in ('Selection', 'Many2one')][:4]
    group_xml = ''
    if groupbys:
        items = '\n'.join(
            f'                    <filter name="group_{f["name"]}" string={quoteattr(label(f))} '
            f'context="{{\'group_by\': \'{f["name"]}\'}}"/>'
            for f in groupbys
        )
        group_xml = f'                <group>\n{items}\n                </group>\n'

    return f"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_{mu}_list" model="ir.ui.view">
        <field name="name">{model}.list</field>
        <field name="model">{model}</field>
        <field name="arch" type="xml">
            <list>
{fl(short[:6], '                ')}
            </list>
        </field>
    </record>

    <record id="view_{mu}_form" model="ir.ui.view">
        <field name="name">{model}.form</field>
        <field name="model">{model}</field>
        <field name="arch" type="xml">
            <form>
{header}                <sheet>
                    <group>
                        <group>
{fl(body[:half], '                            ')}
                        </group>
                        <group>
{fl(body[half:], '                            ')}
                        </group>
                    </group>
{notebook}                </sheet>
{chatter_xml}            </form>
        </field>
    </record>

    <record id="view_{mu}_search" model="ir.ui.view">
        <field name="name">{model}.search</field>
        <field name="model">{model}</field>
        <field name="arch" type="xml">
            <search>
{search_fields}
{group_xml}            </search>
        </field>
    </record>

    <record id="action_{mu}" model="ir.actions.act_window">
        <field name="name">{escape(desc)}</field>
        <field name="res_model">{model}</field>
        <field name="view_mode">list,form</field>
    </record>
</odoo>
"""


def render_menus(spec):
    items = [f'    <menuitem id="menu_{spec["module"]}_root" name={quoteattr(spec["name"])} sequence="90"/>']
    for m in spec['models']:
        mu = m['name'].replace('.', '_')
        desc = m.get('description') or m['name']
        items.append(
            f'    <menuitem id="menu_{mu}" name={quoteattr(desc)} '
            f'parent="menu_{spec["module"]}_root" action="action_{mu}"/>'
        )
    return '<?xml version="1.0" encoding="utf-8"?>\n<odoo>\n' + '\n'.join(items) + '\n</odoo>\n'


def render_manifest(spec):
    depends = list(spec.get('depends') or ['base'])
    if any(m.get('chatter') for m in spec['models']) and 'mail' not in depends:
        depends.append('mail')
    data = ['security/ir.model.access.csv']
    data += [f'views/{m["name"].replace(".", "_")}_views.xml' for m in spec['models']]
    data.append('views/menus.xml')
    manifest = {
        'name': spec['name'],
        'version': '19.0.1.0.0',
        'summary': spec.get('summary', ''),
        'author': spec.get('author', ''),
        'depends': depends,
        'data': data,
        'application': True,
        'installable': True,
        'license': 'LGPL-3',
    }
    return '{\n' + ''.join(f'    {k!r}: {v!r},\n' for k, v in manifest.items()) + '}\n'


def generate(spec, force=False):
    out = ADDONS / spec['module']
    if out.exists() and not force:
        sys.exit(f'{out} already exists. Use --force to overwrite.')
    (out / 'models').mkdir(parents=True, exist_ok=True)
    (out / 'views').mkdir(exist_ok=True)
    (out / 'security').mkdir(exist_ok=True)

    files = {
        '__init__.py': 'from . import models\n',
        '__manifest__.py': render_manifest(spec),
        'models/__init__.py': ''.join(
            f'from . import {m["name"].replace(".", "_")}\n' for m in spec['models']
        ),
        'security/ir.model.access.csv': render_acl(spec),
        'views/menus.xml': render_menus(spec),
    }
    for m in spec['models']:
        mu = m['name'].replace('.', '_')
        files[f'models/{mu}.py'] = render_model_py(m)
        files[f'views/{mu}_views.xml'] = render_views(m)

    for rel, content in files.items():
        (out / rel).write_text(content, encoding='utf-8')
        print(f'  wrote {out.relative_to(ROOT) / rel}')
    return out


# ---------------------------------------------------------------- install test
def run_install(module, db):
    """Install the module into a throwaway database and scan the log for errors."""
    cmd = [
        'docker', 'compose', 'exec', '-T', 'web', 'odoo',
        '-d', db, '-i', module, '--without-demo=all',
        '--db_host=db', '--db_user=odoo', '--db_password=odoo', '--stop-after-init',
    ]
    print(f'\nInstalling {module} into test database {db!r} (first run can take a minute)...')
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    bad = [
        line for line in output.splitlines()
        if ' ERROR ' in line or ' CRITICAL ' in line or 'Traceback' in line
    ]
    if proc.returncode == 0 and not bad:
        print('PASS: module installed without errors')
        return True
    print('FAIL: installation reported problems')
    for line in (bad or output.splitlines())[-15:]:
        print('  ', line)
    return False


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('spec', help='path to the JSON spec')
    ap.add_argument('--lint-only', action='store_true', help='only validate the spec')
    ap.add_argument('--force', action='store_true', help='overwrite an existing module folder')
    ap.add_argument('--install', action='store_true', help='install into a throwaway test database')
    ap.add_argument('--db', default='scaffold_test', help='test database name (default: scaffold_test)')
    args = ap.parse_args()

    try:
        spec = json.loads(Path(args.spec).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f'Cannot read spec: {e}')

    errors = lint(spec)
    if errors:
        print('Spec validation FAILED:')
        for err in errors:
            print(f'  - {err}')
        sys.exit(1)
    print('Spec validation OK')
    if args.lint_only:
        return

    print(f'Generating module {spec["module"]}:')
    generate(spec, force=args.force)

    if args.install and not run_install(spec['module'], args.db):
        sys.exit(1)


if __name__ == '__main__':
    main()