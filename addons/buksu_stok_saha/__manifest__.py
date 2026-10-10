{
    'name': 'Buksu Saha Stok Yönetimi',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'summary': 'Saha malzeme ve stok yönetimi: proje bazlı saha depoları, malzeme talebi ve hareket takibi',
    'description': """
        Buksutrafik ERP saha malzeme ve stok yönetimi:
        - Saha depoları (proje bazlı geçici lokasyonlar, stock.location.is_saha_depo)
        - Stok hareketlerini projeye ve sorumlu ekibe bağlama (stock.picking)
        - Proje bazlı malzeme hareket raporu
        - Saha ekibi malzeme talep sihirbazı (otomatik transfer emri)
        - Saha ekibi / depo sorumlusu yetki ayrımı (record rules)
    """,
    'author': 'Yasin Karacam',
    'category': 'Inventory/Inventory',
    'depends': ['stock', 'project'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/stock_location_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_move_views.xml',
        'views/project_views.xml',
        'wizard/saha_talep_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
}
