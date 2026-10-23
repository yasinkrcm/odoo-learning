from odoo import fields, models


class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Book'

    name = fields.Char(string='Title', required=True)
    author = fields.Char(string='Author')
    isbn = fields.Char(string='ISBN')
    available = fields.Boolean(string='Available', default=True)
