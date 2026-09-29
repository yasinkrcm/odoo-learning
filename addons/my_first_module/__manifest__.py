{
    'name': 'My First Module',
    'version': '1.0',
    'summary': 'Simple todo list module for learning Odoo',
    'description': 'A minimal module to learn Odoo module structure.',
    'author': 'Yasin Karacam',
    'category': 'Productivity',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/todo_views.xml',
        'views/res_partner_views.xml',
        'views/todo_wizard_views.xml',
        'views/todo_reports.xml',
    ],
    'installable': True,
    'application': True,
}