{
    'name': 'Mini Helpdesk',
    'version': '19.0.1.0.0',
    'summary': 'Support tickets with stages, chatter and SLA alerts',
    'depends': ['mail', 'telegram_notify'],
        'data': [
        'security/ir.model.access.csv',
        'data/sequence_stage.xml',
        'views/ticket_views.xml',
        'data/cron.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}