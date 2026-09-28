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
    ],
    'installable': True,
    'application': True,
}