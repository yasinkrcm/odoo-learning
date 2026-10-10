from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    is_saha_depo = fields.Boolean(
        string='Saha Deposu',
        help='Bu lokasyon proje bazlı geçici bir saha deposudur.')
    proje_id = fields.Many2one(
        'project.project', string='İlgili Proje',
        help='Bu saha deposunun ait olduğu proje.')

    @api.depends('complete_name', 'is_saha_depo')
    def _compute_display_name(self):
        for loc in self:
            name = loc.complete_name or loc.name
            if loc.is_saha_depo:
                name = f'[Saha] {name}'
            loc.display_name = name
