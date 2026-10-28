{
    'name': 'Sales Insights',
    'version': '19.0.1.0.0',
    'summary': 'SQL-view based sales analysis with pivot/graph and weekly Telegram summary',
    'depends': ['sale', 'telegram_notify', 'finance_ticker', 'stock', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/sales_analysis_views.xml',
        'data/cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sales_insights/static/src/ask.js',
            'sales_insights/static/src/ask.xml',
        ],
    },
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}