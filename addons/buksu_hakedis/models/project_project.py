from odoo import _, api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    hakedis_donem_ids = fields.One2many(
        'buksu.hakedis.donem', 'proje_id', string='Hakediş Dönemleri')
    hakedis_donem_sayisi = fields.Integer(
        string='Hakediş Sayısı', compute='_compute_hakedis_donem_sayisi')

    @api.depends('hakedis_donem_ids')
    def _compute_hakedis_donem_sayisi(self):
        for proje in self:
            proje.hakedis_donem_sayisi = len(proje.hakedis_donem_ids)

    def action_view_hakedis_donem(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hakediş Dönemleri'),
            'res_model': 'buksu.hakedis.donem',
            'view_mode': 'list,form',
            'domain': [('proje_id', '=', self.id)],
            'context': {'default_proje_id': self.id},
        }
