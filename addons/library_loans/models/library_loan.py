from odoo import fields, models


class LibraryLoan(models.Model):
    _name = 'library.loan'
    _description = 'Loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, tracking=True)
    book_id = fields.Many2one('library.book', string='Book', required=True, tracking=True)
    member_id = fields.Many2one('res.partner', string='Member', tracking=True)
    loan_date = fields.Date(string='Loan Date', tracking=True)
    due_date = fields.Date(string='Due Date', tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('lent', 'Lent'), ('returned', 'Returned')], string='State', default='draft', tracking=True)
    fee = fields.Float(string='Late Fee', tracking=True)
    note = fields.Text(string='Note')
