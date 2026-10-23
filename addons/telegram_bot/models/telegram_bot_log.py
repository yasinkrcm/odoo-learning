from odoo import fields, models


class TelegramBotLog(models.Model):
    _name = 'telegram.bot.log'
    _description = 'Telegram Bot Message Log'
    _order = 'id desc'

    chat_id = fields.Char(string='Chat ID')
    username = fields.Char(string='Telegram User')
    command = fields.Char(string='Command')
    reply = fields.Text(string='Reply')
    handled_at = fields.Datetime(string='Handled At', default=fields.Datetime.now)
