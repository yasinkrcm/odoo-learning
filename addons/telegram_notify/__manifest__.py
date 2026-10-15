{
    'name': 'Telegram Notify',
    'version': '19.0.1.0.0',
    'summary': 'Telegram notifications for sales and overdue invoices',
    'depends': ['sale', 'account'],
    'data': [
        'data/cron.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}