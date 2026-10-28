from odoo import fields, models


class TelegramBotFlow(models.Model):
    _name = 'telegram.bot.flow'
    _description = 'Telegram Bot Step-by-step Flow'
    _order = 'id desc'

    chat_id = fields.Char(string='Chat ID', required=True, index=True)
    step = fields.Selection([
        ('title', 'Title'),
        ('partner', 'Customer'),
        ('priority', 'Priority'),
        ('assignee', 'Assignee'),
        ('description', 'Description'),
        ('attachment', 'Attachment'),
    ], string='Step', required=True, default='title')
    title = fields.Char(string='Title')
    partner_id = fields.Many2one('res.partner', string='Customer')
    priority = fields.Selection([
        ('0', 'Low'), ('1', 'Normal'), ('2', 'High'), ('3', 'Urgent'),
    ], string='Priority')
    user_id = fields.Many2one('res.users', string='Assigned To')
    description = fields.Text(string='Description')
    attachment_name = fields.Char(string='Attachment Name')
    attachment_data = fields.Binary(string='Attachment Data')
    create_uid = fields.Many2one('res.users', string='Telegram User', readonly=True)
