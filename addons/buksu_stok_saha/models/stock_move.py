from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    proje_id = fields.Many2one(
        'project.project', string='Proje', index=True,
        related='picking_id.proje_id', store=True, readonly=True,
        help='Hareketin bağlı olduğu proje (depo fişinden gelir).')
    sorumlu_ekip = fields.Char(
        string='Sorumlu Ekip', related='picking_id.sorumlu_ekip', store=True,
        readonly=True)
