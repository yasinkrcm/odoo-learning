from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_nisa_sync_to_pos(self):
        """Varyant formundaki buton için: işlemi ürün şablonuna yönlendirir."""
        return self.product_tmpl_id.action_nisa_sync_to_pos()