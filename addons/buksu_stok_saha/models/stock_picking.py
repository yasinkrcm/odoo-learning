from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    proje_id = fields.Many2one(
        'project.project', string='Proje', index=True,
        help='Bu saha malzeme hareketinin bağlı olduğu proje.')
    sorumlu_ekip = fields.Char(
        string='Sorumlu Ekip',
        help='Malzemeyi sahada teslim alacak / kullanacak ekip.')
