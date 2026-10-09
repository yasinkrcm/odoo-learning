from odoo import SUPERUSER_ID, api, fields, models


class NisaSyncLog(models.Model):
    _name = 'nisa.sync.log'
    _description = 'NISA POS Senkronizasyon Logu'
    _order = 'date desc, id desc'

    date = fields.Datetime('Tarih', default=fields.Datetime.now, required=True, readonly=True)
    product_tmpl_id = fields.Many2one(
        'product.template', 'Ürün', ondelete='set null', readonly=True, index=True)
    product_name = fields.Char('Ürün Adı', readonly=True,
                               help='Ürün silinse bile log üzerinde kalır.')
    operation = fields.Selection([
        ('push', 'Odoo → POS (Ürün/Stok Gönderimi)'),
        ('webhook_sale', 'POS → Odoo (Satış Webhook)'),
    ], string='İşlem Tipi', required=True, readonly=True)
    status = fields.Selection([
        ('success', 'Başarılı'),
        ('failed', 'Başarısız'),
    ], string='Durum', required=True, readonly=True)
    message = fields.Text('Mesaj', readonly=True)

    @api.model
    def log_independent(self, vals_list):
        """Logu ayrı bir cursor ile yazar. Ana işlem UserError ile geri alınsa
        bile (rollback) log kaydı kaybolmaz."""
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env['nisa.sync.log'].create(vals_list)
