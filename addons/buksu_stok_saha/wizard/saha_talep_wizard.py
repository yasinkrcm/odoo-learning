from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BuksuSahaTalepWizard(models.TransientModel):
    _name = 'buksu.saha.talep.wizard'
    _description = 'Saha Malzeme Talep Sihirbazı'

    proje_id = fields.Many2one(
        'project.project', string='Proje', required=True,
        default=lambda self: self.env.context.get('default_proje_id'))
    hedef_saha_depo_id = fields.Many2one(
        'stock.location', string='Saha Deposu (Hedef)',
        required=True,
        domain=[('is_saha_depo', '=', True), ('usage', '=', 'internal')],
        help='Malzemenin teslim edileceği saha deposu.')
    kaynak_depo_id = fields.Many2one(
        'stock.location', string='Kaynak Depo', required=True,
        domain=[('usage', '=', 'internal')],
        default=lambda self: self._default_kaynak_depo_id())
    sorumlu_ekip = fields.Char(string='Sorumlu Ekip')
    talep_tarihi = fields.Date(
        string='Talep Tarihi', default=fields.Date.context_today,
        required=True)
    aciklama = fields.Text(string='Açıklama')
    satir_ids = fields.One2many(
        'buksu.saha.talep.wizard.satir', 'wizard_id',
        string='Talep Edilen Malzemeler', copy=True)

    @api.model
    def _default_kaynak_depo_id(self):
        depo = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1)
        return depo.lot_stock_id if depo else False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'hedef_saha_depo_id' in fields_list and not res.get('hedef_saha_depo_id'):
            proje_id = res.get('proje_id')
            if proje_id:
                saha_depo = self.env['stock.location'].search(
                    [('is_saha_depo', '=', True), ('proje_id', '=', proje_id)], limit=1)
                if saha_depo:
                    res['hedef_saha_depo_id'] = saha_depo.id
        return res

    @api.onchange('proje_id')
    def _onchange_proje_id(self):
        if self.proje_id and not self.hedef_saha_depo_id:
            saha_depo = self.env['stock.location'].search(
                [('is_saha_depo', '=', True), ('proje_id', '=', self.proje_id.id)],
                limit=1)
            self.hedef_saha_depo_id = saha_depo

    def action_onayla(self):
        self.ensure_one()
        if not self.satir_ids:
            raise UserError(_('En az bir malzeme kalemi girmelisiniz.'))
        for satir in self.satir_ids:
            if satir.miktar <= 0:
                raise UserError(
                    _('"%s" için girilen miktar sıfırdan büyük olmalıdır.')
                    % satir.urun_id.display_name)

        outgoing_type = self.env['stock.picking.type'].search(
            [('code', '=', 'outgoing'),
             ('company_id', '=', self.env.company.id)], limit=1)
        if not outgoing_type:
            raise UserError(_('Bu şirket için giden (outgoing) operasyon tipi bulunamadı.'))

        picking = self.env['stock.picking'].create({
            'picking_type_id': outgoing_type.id,
            'location_id': self.kaynak_depo_id.id,
            'location_dest_id': self.hedef_saha_depo_id.id,
            'origin': _('Saha Talebi - %s') % self.proje_id.display_name,
            'scheduled_date': fields.Datetime.now(),
            'proje_id': self.proje_id.id,
            'sorumlu_ekip': self.sorumlu_ekip,
            'move_ids': [(0, 0, {
                'product_id': satir.urun_id.id,
                'product_uom_qty': satir.miktar,
                'product_uom': satir.urun_id.uom_id.id,
                'location_id': self.kaynak_depo_id.id,
                'location_dest_id': self.hedef_saha_depo_id.id,
            }) for satir in self.satir_ids],
        })
        picking.action_confirm()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }


class BuksuSahaTalepWizardSatir(models.TransientModel):
    _name = 'buksu.saha.talep.wizard.satir'
    _description = 'Saha Malzeme Talep Satırı'

    wizard_id = fields.Many2one(
        'buksu.saha.talep.wizard', required=True, ondelete='cascade')
    urun_id = fields.Many2one(
        'product.product', string='Malzeme', required=True,
        domain=[('is_storable', '=', True)])
    miktar = fields.Float(string='Miktar', required=True, digits='Product Unit of Measure')
    uom_id = fields.Many2one(
        'uom.uom', string='Birim', related='urun_id.uom_id', readonly=True)
    mevcut_stok = fields.Float(
        string='Mevcut Stok', compute='_compute_mevcut_stok',
        digits='Product Unit of Measure')

    @api.depends('urun_id', 'wizard_id.kaynak_depo_id')
    def _compute_mevcut_stok(self):
        for satir in self:
            if satir.urun_id and satir.wizard_id.kaynak_depo_id:
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', satir.urun_id.id),
                    ('location_id', '=', satir.wizard_id.kaynak_depo_id.id),
                ], limit=1)
                satir.mevcut_stok = quant.available_quantity
            else:
                satir.mevcut_stok = 0.0
