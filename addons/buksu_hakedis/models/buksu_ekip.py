from odoo import fields, models


class BuksuEkip(models.Model):
    _name = 'buksu.ekip'
    _description = 'Hakediş Ekibi (Taşeron)'
    _order = 'name'

    name = fields.Char(string='Ekip Adı', required=True)
    active = fields.Boolean(string='Aktif', default=True)
    partner_id = fields.Many2one(
        'res.partner', string='Taşeron / Tedarikçi Partneri', required=True,
        help='Hakediş faturasının kesileceği partner.')
    sorumlu_id = fields.Many2one('res.users', string='Ekip Sorumlusu')
    aciklama = fields.Text(string='Açıklama')
    company_id = fields.Many2one(
        'res.company', string='Şirket', default=lambda self: self.env.company)

    _name_uniq = models.Constraint(
        'UNIQUE(name)', 'Bu ekip adı zaten kayıtlı.')
