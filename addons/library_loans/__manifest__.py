{
    'name': 'Library Loans',
    'version': '19.0.1.0.0',
    'summary': 'Track books and who borrowed them',
    'author': '',
    'depends': ['base', 'mail'],
    'data': ['security/ir.model.access.csv', 'views/library_book_views.xml', 'views/library_loan_views.xml', 'views/menus.xml'],
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
