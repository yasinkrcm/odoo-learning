from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# durum geçiş sırası: geriye geçiş (küçülme) yasaktır
DURUM_SIRA = {
    'taslak': 0,
    'onaylandi': 1,
    'odendi': 2,
}


class BuksuHakedisDonem(models.Model):
    _name = 'buksu.hakedis.donem'
    _description = 'Hakediş Dönemi'
    _order = 'tarih_baslangic desc, id desc'

    name = fields.Char(string='Hakediş No', copy=False, index=True)
    proje_id = fields.Many2one(
        'project.project', string='Proje', required=True, index=True)
    ekip_id = fields.Many2one(
        'buksu.ekip', string='Ekip', required=True, index=True)
    tarih_baslangic = fields.Date(string='Dönem Başlangıcı', required=True)
    tarih_bitis = fields.Date(string='Dönem Bitişi', required=True)
    durum = fields.Selection(
        selection=[
            ('taslak', 'Taslak'),
            ('onaylandi', 'Onaylandı'),
            ('odendi', 'Ödendi'),
        ],
        string='Durum', required=True, default='taslak', index=True)
    satir_ids = fields.One2many(
        'buksu.hakedis.satir', 'donem_id', string='Hakediş Satırları')
    brut_toplam = fields.Monetary(
        string='Brüt Toplam', compute='_compute_brut_toplam', store=True)
    kesinti_tutari = fields.Monetary(
        string='Kesinti Tutarı', compute='_compute_kesinti_tutari', store=True)
    net_tutar = fields.Monetary(
        string='Net Ödenecek Tutar', compute='_compute_net_tutar', store=True)
    aciklama = fields.Text(string='Açıklama')
    fatura_id = fields.Many2one(
        'account.move', string='Fatura', readonly=True, copy=False,
        check_company=True, domain=[('move_type', '=', 'in_invoice')],
        help='Bu hakediş döneminden oluşturulan satıcı faturası.')
    fatura_durumu = fields.Selection(
        related='fatura_id.payment_state', string='Fatura Durumu')
    ekip_partner_id = fields.Many2one(
        related='ekip_id.partner_id', string='Taşeron / Tedarikçi Partneri',
        readonly=False)
    company_id = fields.Many2one(
        'res.company', string='Şirket', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Para Birimi')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'buksu.hakedis.donem') or _('Yeni')
        return super().create(vals_list)

    def write(self, vals):
        if 'durum' in vals:
            yeni_sira = DURUM_SIRA.get(vals['durum'])
            if yeni_sira is not None:
                for rec in self:
                    if yeni_sira < DURUM_SIRA[rec.durum]:
                        raise UserError(_(
                            "Hakediş durumu geri alınamaz: '%(donem)s' kaydı "
                            "'%(eski)s' durumundan '%(yeni)s' durumuna geçemez.",
                            donem=rec.display_name,
                            eski=dict(self._fields['durum'].selection).get(rec.durum),
                            yeni=dict(self._fields['durum'].selection).get(vals['durum']),
                        ))
        return super().write(vals)

    @api.constrains('tarih_baslangic', 'tarih_bitis')
    def _check_tarihler(self):
        for rec in self:
            if rec.tarih_baslangic and rec.tarih_bitis and rec.tarih_bitis < rec.tarih_baslangic:
                raise ValidationError(
                    _('Dönem bitiş tarihi başlangıç tarihinden önce olamaz.'))

    @api.depends('satir_ids.toplam')
    def _compute_brut_toplam(self):
        for rec in self:
            rec.brut_toplam = rec.currency_id.round(
                sum(rec.satir_ids.mapped('toplam')))

    @api.depends('satir_ids.toplam', 'satir_ids.kesinti_yuzdesi')
    def _compute_kesinti_tutari(self):
        for rec in self:
            rec.kesinti_tutari = sum(
                rec.currency_id.round(
                    satir.toplam * satir.kesinti_yuzdesi / 100.0)
                for satir in rec.satir_ids)

    @api.depends('brut_toplam', 'kesinti_tutari')
    def _compute_net_tutar(self):
        for rec in self:
            rec.net_tutar = rec.currency_id.round(
                rec.brut_toplam - rec.kesinti_tutari)

    def action_onayla(self):
        for rec in self:
            if rec.durum != 'taslak':
                raise UserError(_(
                    "Sadece taslak durumundaki hakediş onaylanabilir: %s")
                    % rec.display_name)
            if not rec.satir_ids:
                raise UserError(_(
                    "Onaylanacak hakediş satırı yok, önce iş kalemlerini girin: %s")
                    % rec.display_name)
            rec.durum = 'onaylandi'
        return True

    def action_odeme_yap(self):
        for rec in self:
            if rec.durum != 'onaylandi':
                raise UserError(_(
                    "Sadece onaylanmış hakediş ödendi olarak işaretlenebilir: %s")
                    % rec.display_name)
            rec.durum = 'odendi'
        return True

    def action_fatura_olustur(self):
        self.ensure_one()
        if self.durum not in ('onaylandi', 'odendi'):
            raise UserError(_(
                "Fatura sadece onaylanmış hakediş için oluşturulabilir: %s")
                % self.display_name)
        if self.fatura_id:
            raise UserError(_("Bu hakediş için zaten fatura oluşturulmuş: %s")
                            % self.fatura_id.display_name)
        if not self.ekip_id.partner_id:
            raise UserError(_(
                "Fatura için önce ekip kaydında taşeron partneri seçin: %s")
                % self.ekip_id.display_name)
        if not self.satir_ids:
            raise UserError(_("Hakediş satırı olmadan fatura oluşturulamaz."))
        satir_degerleri = [(0, 0, {
            'name': satir.is_kalemi + (' (%s)' % satir.birim if satir.birim else ''),
            'quantity': satir.miktar,
            'price_unit': satir.birim_fiyat,
            'discount': satir.kesinti_yuzdesi,
        }) for satir in self.satir_ids]
        fatura = self.env['account.move'].sudo().create({
            'move_type': 'in_invoice',
            'partner_id': self.ekip_id.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': self.name,
            'invoice_line_ids': satir_degerleri,
            'company_id': self.company_id.id,
        })
        self.fatura_id = fatura
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hakediş Faturası'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': fatura.id,
        }

    def action_view_fatura(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hakediş Faturası'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.fatura_id.id,
        }


class BuksuHakedisSatir(models.Model):
    _name = 'buksu.hakedis.satir'
    _description = 'Hakediş Satırı (İş Kalemi)'
    _order = 'donem_id, id'

    donem_id = fields.Many2one(
        'buksu.hakedis.donem', string='Hakediş Dönemi',
        required=True, ondelete='cascade', index=True)
    is_kalemi = fields.Char(string='İş Kalemi', required=True)
    birim = fields.Char(
        string='Metraj Birimi', help='m², m³, adet, kg, ton vb.')
    miktar = fields.Float(string='Metraj Miktarı', digits=(12, 3))
    birim_fiyat = fields.Monetary(string='Birim Fiyat')
    kesinti_yuzdesi = fields.Float(
        string='Kesinti %', digits=(12, 2), default=0.0)
    toplam = fields.Monetary(
        string='Satır Toplamı', compute='_compute_toplam', store=True)
    aciklama = fields.Text(string='Satır Açıklaması')
    currency_id = fields.Many2one(
        related='donem_id.currency_id', string='Para Birimi')
    company_id = fields.Many2one(
        related='donem_id.company_id', string='Şirket', store=True)

    @api.depends('miktar', 'birim_fiyat')
    def _compute_toplam(self):
        for satir in self:
            satir.toplam = satir.currency_id.round(
                (satir.miktar or 0.0) * (satir.birim_fiyat or 0.0))

    @api.constrains('miktar', 'birim_fiyat', 'kesinti_yuzdesi')
    def _check_degerler(self):
        for satir in self:
            if satir.miktar < 0:
                raise ValidationError(_(
                    'Metraj miktarı negatif olamaz: %s') % satir.is_kalemi)
            if satir.birim_fiyat < 0:
                raise ValidationError(_(
                    'Birim fiyat negatif olamaz: %s') % satir.is_kalemi)
            if not 0 <= satir.kesinti_yuzdesi <= 100:
                raise ValidationError(_(
                    'Kesinti yüzdesi 0-100 arasında olmalıdır: %s')
                    % satir.is_kalemi)

    def _check_donem_taslak(self):
        for satir in self:
            if satir.donem_id.durum != 'taslak':
                raise UserError(_(
                    "'%s' dönemi onaylandığı/ödendiği için hakediş satırları "
                    "değiştirilemez.") % satir.donem_id.display_name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            donem = self.env['buksu.hakedis.donem'].browse(vals.get('donem_id'))
            if donem.durum != 'taslak':
                raise UserError(_(
                    "'%s' dönemi onaylandığı/ödendiği için hakediş satırları "
                    "değiştirilemez.") % donem.display_name)
        return super().create(vals_list)

    def write(self, vals):
        self._check_donem_taslak()
        return super().write(vals)

    def unlink(self):
        self._check_donem_taslak()
        return super().unlink()
