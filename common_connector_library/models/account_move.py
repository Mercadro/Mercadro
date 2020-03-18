from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Added By Dimpal on 5/oct/2019
    global_channel_id = fields.Many2one('global.channel.ept', string='Global Channel')

    @api.model
    def create(self, vals):
        """This function is inherit for set global channel in journal entries...
            @author: Dimpal added on 7/oct/2019
        """
        # used for set global channel when create valuation entries...
        if vals.get('line_ids') and vals.get('line_ids')[0][2]\
                and vals.get('line_ids')[0][2].get('global_channel_id'):
            vals.update({'global_channel_id': vals.get('line_ids')[0][2].get('global_channel_id')})

        res = super(AccountMove, self).create(vals)
        for line in res.line_ids:
            if not line.global_channel_id and res.global_channel_id:
                line.global_channel_id = res.global_channel_id.id
        return res
