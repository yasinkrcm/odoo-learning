from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    saha_kullanici_ids = fields.Many2many(
        'res.users', 'buksu_saha_project_user_rel', 'project_id', 'user_id',
        string='Saha Ekibi Kullanıcıları',
        help='Bu projenin saha hareketlerini görebilecek saha ekibi kullanıcıları.')
    malzeme_hareket_sayisi = fields.Integer(
        string='Malzeme Hareketi', compute='_compute_malzeme_hareket_sayisi')

    def _compute_malzeme_hareket_sayisi(self):
        for proje in self:
            proje.malzeme_hareket_sayisi = self.env['stock.move'].search_count(
                [('picking_id.proje_id', '=', proje.id)])

    def action_view_malzeme_hareketleri(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Proje Malzeme Hareketleri',
            'res_model': 'stock.move',
            'view_mode': 'list,form',
            'domain': [('picking_id.proje_id', '=', self.id)],
            'context': {'default_proje_id': self.id},
        }
