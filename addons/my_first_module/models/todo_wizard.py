from odoo import models, fields


class TodoDeadlineWizard(models.TransientModel):
    _name = 'my.todo.deadline.wizard'
    _description = 'Set Deadline Wizard'

    deadline = fields.Date(string='New Deadline', required=True)

    def action_apply(self):
        active_ids = self.env.context.get('active_ids', [])
        todos = self.env['my.todo'].browse(active_ids)
        todos.write({'deadline': self.deadline})
        return {'type': 'ir.actions.act_window_close'}