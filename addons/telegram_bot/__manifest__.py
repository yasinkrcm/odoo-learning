{
    'name': 'Telegram Bot',
    'version': '19.0.1.0.0',
    'summary': 'İki yönlü Telegram botu: adım adım bilet, sorgular, KPI raporu',
    'description': """
Two-way Telegram bridge for Odoo 19.
Receives updates via webhook (VPS) or getUpdates polling (local cron),
dispatches white-listed user commands and replies in HTML:
/siparis, /stok, /musteri, /rapor, /bilet (mini_helpdesk optional),
/yardim. Incoming updates are audited in telegram.bot.log.
Uses the bot token configured for telegram_notify.
""",
    'depends': ['base', 'mail', 'telegram_notify', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/telegram_bot_log_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
