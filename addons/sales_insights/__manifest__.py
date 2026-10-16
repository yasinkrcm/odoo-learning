{
    'name': 'Sales Insights',
    'version': '19.0.1.0.0',
    'summary': 'SQL-view based sales analysis with pivot/graph and weekly Telegram summary',
    'depends': ['sale', 'telegram_notify'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/sales_analysis_views.xml',
        'data/cron.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}