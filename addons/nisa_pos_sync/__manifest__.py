{
    'name': 'NISA POS Sync',
    'version': '19.0.1.0.0',
    'summary': 'Odoo ile harici POS arasında ürün ve stok senkronizasyonu',
    'category': 'Inventory',
    'author': 'Yasin Karacam',
    'license': 'LGPL-3',
    'depends': ['product'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/product_template_views.xml',
        'views/nisa_sync_log_views.xml',
    ],
    'installable': True,
    'application': False,
}
