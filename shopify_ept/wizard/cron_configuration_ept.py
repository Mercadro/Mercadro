from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta

_intervalTypes = {
    'work_days': lambda interval: relativedelta(days=interval),
    'days': lambda interval: relativedelta(days=interval),
    'hours': lambda interval: relativedelta(hours=interval),
    'weeks': lambda interval: relativedelta(days=7 * interval),
    'months': lambda interval: relativedelta(months=interval),
    'minutes': lambda interval: relativedelta(minutes=interval),
}


class ShopifyCronConfigurationEpt(models.TransientModel):
    """
    Common model for manage cron configuration
    """
    _name = "shopify.cron.configuration.ept"
    _description = "Shopify Cron Configuration Ept"

    def _get_shopify_instance(self):
        return self.env.context.get('shopify_instance_id', False)

    shopify_instance_id = fields.Many2one('shopify.instance.ept', 'Shopify Instance',
                                          help="Select Shopify Instance that you want to configure.",
                                          default=_get_shopify_instance, readonly=True)

    # Auto cron for Export stock
    shopify_stock_auto_export = fields.Boolean('Export Stock', default=False,
                                               help="Check if you want to automatically Export Stock levels from Odoo to Shopify.")
    shopify_inventory_export_interval_number = fields.Integer('Interval Number for Export stock', help="Repeat every x.")
    shopify_inventory_export_interval_type = fields.Selection([('minutes', 'Minutes'),
                                                               ('hours', 'Hours'), ('work_days', 'Work Days'),
                                                               ('days', 'Days'), ('weeks', 'Weeks'),
                                                               ('months', 'Months')], 'Interval Unit for Export Stock')
    shopify_inventory_export_next_execution = fields.Datetime('Next Execution for Export Stock ', help='Next Execution for Export Stock')
    shopify_inventory_export_user_id = fields.Many2one('res.users', string="User for Export Inventory", help='User for Export Inventory',
                                                       default=lambda self: self.env.user)

    # Auto cron for Import Order
    shopify_order_auto_import = fields.Boolean('Import Order', default=False,
                                               help="Check if you want to automatically Import Orders from Shopify to Odoo.")
    shopify_import_order_interval_number = fields.Integer('Interval Number for Import Order', help="Repeat every x.")
    shopify_import_order_interval_type = fields.Selection([('minutes', 'Minutes'),
                                                           ('hours', 'Hours'), ('work_days', 'Work Days'),
                                                           ('days', 'Days'), ('weeks', 'Weeks'),
                                                           ('months', 'Months')], 'Interval Unit for Import Order')
    shopify_import_order_next_execution = fields.Datetime('Next Execution for Import Order', help='Next Execution for Import Order')
    shopify_import_order_user_id = fields.Many2one('res.users', string="User for Import Order", help='User for Import Order',
                                                   default=lambda self: self.env.user)

    # Auto cron for Update Order Status
    shopify_order_status_auto_update = fields.Boolean('Update Order Status', default=False,
                                                      help="Check if you want to automatically Update Order Status from Shopify to Odoo.")
    shopify_order_status_interval_number = fields.Integer('Interval Number for Update Order Status', help="Repeat every x.")
    shopify_order_status_interval_type = fields.Selection([('minutes', 'Minutes'),
                                                           ('hours', 'Hours'), ('work_days', 'Work Days'),
                                                           ('days', 'Days'), ('weeks', 'Weeks'),
                                                           ('months', 'Months')], 'Interval Unit for Update Order Status')
    shopify_order_status_next_execution = fields.Datetime('Next Execution for Update Order Status', help='Next Execution for Update Order Status')
    shopify_order_status_user_id = fields.Many2one('res.users', string="User for Update Order Status", help='User for Update Order Status',
                                                   default=lambda self: self.env.user)

    @api.onchange("shopify_instance_id")
    def onchange_shopify_instance_id(self):
        """
        Set field value while open the wizard
        :param instance:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 16/11/2019.
        Task Id : 157716
        """
        instance = self.shopify_instance_id
        self.update_export_stock_cron_field(instance)
        self.update_import_order_cron_field(instance)
        self.update_order_status_cron_field(instance)

    def update_export_stock_cron_field(self, instance):
        """
        Update and set the 'Export Inventory Stock' cron field while open the wizard
        :param instance:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 16/11/2019.
        Task Id : 157716
        """
        try:
            export_inventory_stock_cron_exist = instance and self.env.ref(
                'shopify_ept.ir_cron_shopify_auto_export_inventory_instance_%d' % (instance.id))
        except:
            export_inventory_stock_cron_exist = False
        if export_inventory_stock_cron_exist:
            self.shopify_stock_auto_export = export_inventory_stock_cron_exist.active or False
            self.shopify_inventory_export_interval_number = export_inventory_stock_cron_exist.interval_number or False
            self.shopify_inventory_export_interval_type = export_inventory_stock_cron_exist.interval_type or False
            self.shopify_inventory_export_next_execution = export_inventory_stock_cron_exist.nextcall or False
            self.shopify_inventory_export_user_id = export_inventory_stock_cron_exist.user_id.id or False

    def update_import_order_cron_field(self, instance):
        """
        Update and set the 'Import Sale Orders' cron field while open the wizard
        :param instance:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 16/11/2019.
        Task Id : 157716
        """
        try:
            import_order_cron_exist = instance and self.env.ref(
                'shopify_ept.ir_cron_shopify_auto_import_order_instance_%d' % (instance.id))
        except:
            import_order_cron_exist = False
        if import_order_cron_exist:
            self.shopify_order_auto_import = import_order_cron_exist.active or False
            self.shopify_import_order_interval_number = import_order_cron_exist.interval_number or False
            self.shopify_import_order_interval_type = import_order_cron_exist.interval_type or False
            self.shopify_import_order_next_execution = import_order_cron_exist.nextcall or False
            self.shopify_import_order_user_id = import_order_cron_exist.user_id.id or False

    def update_order_status_cron_field(self, instance):
        """
        Update and set the 'Update Order Status' cron field while open the wizard
        :param instance:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 16/11/2019.
        Task Id : 157716
        """
        try:
            update_order_status_cron_exist = instance and self.env.ref(
                'shopify_ept.ir_cron_shopify_auto_update_order_status_instance_%d' % (instance.id))
        except:
            update_order_status_cron_exist = False
        if update_order_status_cron_exist:
            self.shopify_order_status_auto_update = update_order_status_cron_exist.active or False
            self.shopify_order_status_interval_number = update_order_status_cron_exist.interval_number or False
            self.shopify_order_status_interval_type = update_order_status_cron_exist.interval_type or False
            self.shopify_order_status_next_execution = update_order_status_cron_exist.nextcall or False
            self.shopify_order_status_user_id = update_order_status_cron_exist.user_id.id or False

    def save(self):
        """
        Save method for auto cron
        :param instance:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 16/11/2019.
        Task Id : 157716
        """
        instance_id = self._context.get('shopify_instance_id')
        instance = self.env['shopify.instance.ept'].browse(instance_id)
        self.setup_shopify_inventory_export_cron(instance)
        self.setup_shopify_import_order_cron(instance)
        self.setup_shopify_update_order_status_cron(instance)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def setup_shopify_inventory_export_cron(self, instance):
        """
        Cron for auto Export Inventory Stock
        :param instance:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 16/11/2019.
        Task Id : 157716
        """
        if self.shopify_stock_auto_export:
            try:
                cron_exist = self.env.ref('shopify_ept.ir_cron_shopify_auto_export_inventory_instance_%d' % (instance.id))
            except:
                cron_exist = False
            nextcall = datetime.now()
            nextcall += _intervalTypes[self.shopify_inventory_export_interval_type](
                self.shopify_inventory_export_interval_number)
            vals = {'active': True,
                    'interval_number': self.shopify_inventory_export_interval_number,
                    'interval_type': self.shopify_inventory_export_interval_type,
                    'nextcall': self.shopify_inventory_export_next_execution or nextcall.strftime('%Y-%m-%d %H:%M:%S'),
                    'code': "model.update_stock_in_shopify(ctx={'shopify_instance_id':%d})" % (instance.id),
                    'user_id': self.shopify_inventory_export_user_id and self.shopify_inventory_export_user_id.id}
            if cron_exist:
                vals.update({'name': cron_exist.name})
                cron_exist.write(vals)
            else:
                try:
                    export_stock_cron = self.env.ref('shopify_ept.ir_cron_shopify_auto_export_inventory')
                except:
                    export_stock_cron = False
                if not export_stock_cron:
                    raise Warning(
                        'Core settings of Shopify are deleted, please upgrade Shopify module to back this settings.')

                name = instance.name + ' : ' + export_stock_cron.name
                vals.update({'name': name})
                new_cron = export_stock_cron.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'shopify_ept',
                                                  'name': 'ir_cron_shopify_auto_export_inventory_instance_%d' % (instance.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })

        else:
            try:
                cron_exist = self.env.ref('shopify_ept.ir_cron_shopify_auto_export_inventory_instance_%d' % (instance.id))
            except:
                cron_exist = False
            if cron_exist:
                cron_exist.write({'active': False})
            return True

    def setup_shopify_import_order_cron(self, instance):
        """
        Cron for auto Import Orders
        :param instance:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 16/11/2019.
        Task Id : 157716
        """
        if self.shopify_order_auto_import:
            try:
                cron_exist = self.env.ref('shopify_ept.ir_cron_shopify_auto_import_order_instance_%d' % (instance.id))
            except:
                cron_exist = False
            nextcall = datetime.now()
            nextcall += _intervalTypes[self.shopify_import_order_interval_type](
                self.shopify_import_order_interval_number)
            vals = {'active': True,
                    'interval_number': self.shopify_import_order_interval_number,
                    'interval_type': self.shopify_import_order_interval_type,
                    'nextcall': self.shopify_import_order_next_execution or nextcall.strftime('%Y-%m-%d %H:%M:%S'),
                    'code': "model.import_order_cron_action(ctx={'shopify_instance_id':%d})" % (instance.id),
                    'user_id': self.shopify_import_order_user_id and self.shopify_import_order_user_id.id}
            if cron_exist:
                vals.update({'name': cron_exist.name})
                cron_exist.write(vals)
            else:
                try:
                    import_order_cron = self.env.ref('shopify_ept.ir_cron_shopify_auto_import_order')
                except:
                    import_order_cron = False
                if not import_order_cron:
                    raise Warning(
                        'Core settings of Shopify are deleted, please upgrade Shopify module to back this settings.')

                name = instance.name + ' : ' + import_order_cron.name
                vals.update({'name': name})
                new_cron = import_order_cron.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'shopify_ept',
                                                  'name': 'ir_cron_shopify_auto_import_order_instance_%d' % (instance.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })

        else:
            try:
                cron_exist = self.env.ref('shopify_ept.ir_cron_shopify_auto_import_order_instance_%d' % (instance.id))
            except:
                cron_exist = False
            if cron_exist:
                cron_exist.write({'active': False})
            return True

    def setup_shopify_update_order_status_cron(self, instance):
        """
        Cron for auto Update Order Status
        :param instance:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 16/11/2019.
        Task Id : 157716
        """
        if self.shopify_order_status_auto_update:
            try:
                cron_exist = self.env.ref('shopify_ept.ir_cron_shopify_auto_update_order_status_instance_%d' % (instance.id))
            except:
                cron_exist = False
            nextcall = datetime.now()
            nextcall += _intervalTypes[self.shopify_order_status_interval_type](
                self.shopify_order_status_interval_number)
            vals = {'active': True,
                    'interval_number': self.shopify_order_status_interval_number,
                    'interval_type': self.shopify_order_status_interval_type,
                    'nextcall': self.shopify_order_status_next_execution or nextcall.strftime('%Y-%m-%d %H:%M:%S'),
                    'code': "model.update_order_status_cron_action(ctx={'shopify_instance_id':%d})" % (instance.id),
                    'user_id': self.shopify_order_status_user_id and self.shopify_order_status_user_id.id}
            if cron_exist:
                vals.update({'name': cron_exist.name})
                cron_exist.write(vals)
            else:
                try:
                    update_order_status_cron = self.env.ref('shopify_ept.ir_cron_shopify_auto_update_order_status')
                except:
                    update_order_status_cron = False
                if not update_order_status_cron:
                    raise Warning(
                        'Core settings of Shopify are deleted, please upgrade Shopify module to back this settings.')

                name = instance.name + ' : ' + update_order_status_cron.name
                vals.update({'name': name})
                new_cron = update_order_status_cron.copy(default=vals)
                self.env['ir.model.data'].create({'module': 'shopify_ept',
                                                  'name': 'ir_cron_shopify_auto_update_order_status_instance_%d' % (instance.id),
                                                  'model': 'ir.cron',
                                                  'res_id': new_cron.id,
                                                  'noupdate': True
                                                  })

        else:
            try:
                cron_exist = self.env.ref('shopify_ept.ir_cron_shopify_auto_update_order_status_instance_%d' % (instance.id))
            except:
                cron_exist = False
            if cron_exist:
                cron_exist.write({'active': False})
            return True
