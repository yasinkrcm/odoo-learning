{
    'name': 'Buksu Hakediş Takibi',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'summary': 'Taşeron ekipler için hakediş (ilerleme ödemesi) takibi',
    'description': """
        İnşaat/trafik saha işlerinde taşeron ekiplere yapılan hakediş
        (ilerleme ödemesi) takibini yönetir.
        - Hakediş dönemleri (proje + ekip bazlı)
        - İş kalemi satırları (metraj, birim fiyat, kesinti)
        - Taslak -> Onaylandı -> Ödendi akışı
        - PDF hakediş raporu
    """,
    'author': 'Yasin Karacam',
    'category': 'Project',
    'depends': ['base', 'project', 'web', 'account'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/buksu_hakedis_views.xml',
        'views/buksu_ekip_views.xml',
        'views/project_views.xml',
        'report/buksu_hakedis_report.xml',
    ],
    'installable': True,
    'application': True,
}
