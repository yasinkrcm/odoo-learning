from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    telegram_user_id = fields.Char(string='Telegram User ID', copy=False)
