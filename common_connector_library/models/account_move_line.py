from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    global_channel_id = fields.Many2one('global.channel.ept', string='Global Channel')
