import base64
import csv
import json
import logging
import time
from csv import DictWriter, DictReader
from datetime import datetime, timedelta
from io import StringIO, BytesIO

from odoo.exceptions import Warning, ValidationError
from odoo.tools.misc import split_every

from odoo import models, fields, api, _
from .. import shopify

_logger = logging.getLogger("Shopify")


class ShopifyProcessImportExport(models.TransientModel):
    _name = 'shopify.process.import.export'
    _description = 'Shopify Process Import Export'

    shopify_instance_id = fields.Many2one(
        'shopify.instance.ept', string='Instance')
    sync_product_from_shopify = fields.Boolean("Sync Products")
    shopify_operation = fields.Selection(
        [
            ('sync_product',
             'Sync New Products - Set To Queue'),
            ('sync_product_by_remote_ids',
             'Sync New Products - By Remote Ids'),
            ('import_orders',
             'Import Orders'),
            ('import_orders_by_remote_ids',
             'Import Orders - By Remote Ids'),
            ('update_order_status',
             'Update Order Status'),
            ('import_customers',
             'Import Customers'),
            ('export_stock',
             'Export Stock'),
            ('import_stock',
             'Import Stock'),
            ('update_order_status',
             'Update Order Status')
        ],
        string="Operation",
        default="sync_product")
    orders_from_date = fields.Datetime(string="From Date")
    orders_to_date = fields.Datetime(string="To Date")
    shopify_instance_ids = fields.Many2many(
        "shopify.instance.ept",
        'shopify_instance_import_export_rel',
        'process_id',
        'shopify_instance_id',
        "Instances")
    shopify_is_set_price = fields.Boolean(string="Set Price ?",
                                          help="If is a mark, it set the price with product in the Shopify store.",
                                          default=False)
    shopify_is_set_stock = fields.Boolean(string="Set Stock ?",
                                          help="If is a mark, it set the stock with product in the Shopify store.",
                                          default=False)
    shopify_is_publish = fields.Selection(
        [('publish_product', 'Publish'), ('unpublish_product', 'Unpublish')],
        string="Publish In Website ?",
        help="If is a mark, it publish the product in website.",
        default='publish_product')
    shopify_is_set_image = fields.Boolean(string="Set Image ?",
                                          help="If is a mark, it set the image with product in the Shopify store.",
                                          default=False)
    shopify_is_set_basic_detail = fields.Boolean(string="Set Basic Detail ?",
                                                 help="If is a mark, it set the product basic detail in shopify store",
                                                 default=True)
    shopify_is_update_basic_detail = fields.Boolean(string="Update Basic Detail ?",
                                                    help="If is a mark, it update the product basic detail in shopify store",
                                                    default=False)
    shopify_is_update_price = fields.Boolean(string="set Price ?")
    datas = fields.Binary('File', help="store the choose file data")
    choose_file = fields.Binary(string='Choose File', filters='*.csv',
                                help="select file to upload")
    file_name = fields.Char(string='File Name', help="upload file name")
    shopify_template_ids = fields.Text(string="Template Ids",
                                       help="Based on template ids get product from shopify and import products in odoo")
    shopify_order_ids = fields.Text(string="Order Ids",
                                       help="Based on template ids get product from shopify and import products in odoo")

    def shopify_execute(self):
        """This method used to execute the operation as per given in wizard.
            @param : self
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 25/10/2019.
        """
        product_data_queue_obj = self.env["shopify.product.data.queue.ept"]
        order_date_queue_obj = self.env["shopify.order.data.queue.ept"]

        instance = self.shopify_instance_id
        if self.shopify_operation == 'sync_product':
            product_queues = product_data_queue_obj.shopify_create_product_data_queue(instance)
            if product_queues:
                action = self.env.ref('shopify_ept.action_shopify_product_data_queue').read()[0]
                action['domain'] = [('id', 'in', product_queues)]
                return action
        if self.shopify_operation == 'sync_product_by_remote_ids':
            product_queues = product_data_queue_obj.shopify_create_product_data_queue(instance,
                                                                                      self.shopify_template_ids)
            if product_queues:
                product_data_queue = product_data_queue_obj.browse(product_queues)
                product_data_queue.product_data_queue_lines.process_product_queue_line_data()
                _logger.info(
                    "Processed product queue : {0} of Instance : {1} Via Product Template ids Suuceessfully .".format(
                        product_data_queue.name,
                        instance.name))
                if not product_data_queue.product_data_queue_lines:
                    product_data_queue.unlink()
        if self.shopify_operation == 'import_customers':
            customer_queues = self.sync_shopify_customers()
            if customer_queues:
                action = self.env.ref('shopify_ept.action_shopify_synced_customer_data').read()[0]
                action['domain'] = [('id', 'in', customer_queues)]
                return action
        if self.shopify_operation == 'import_orders':
            order_queues = order_date_queue_obj.shopify_create_order_data_queues(instance,
                                                                                 self.orders_from_date,
                                                                                 self.orders_to_date)
            if order_queues:
                action = self.env.ref('shopify_ept.action_shopify_order_data_queue_ept').read()[0]
                action['domain'] = [('id', 'in', order_queues)]
                return action
        if self.shopify_operation == 'import_orders_by_remote_ids':
            order_date_queue_obj.import_order_process_by_remote_ids(instance, self.shopify_order_ids)
        if self.shopify_operation == 'export_stock':
            self.update_stock_in_shopify(instance)
        if self.shopify_operation == 'import_stock':
            self.import_stock_in_odoo()
        if self.shopify_operation == 'update_order_status':
            self.update_order_status_in_shopify(instance=False)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def manual_export_product_to_shopify(self):
        start = time.time()
        shopify_product_template_obj = self.env['shopify.product.template.ept']
        shopify_product_obj = self.env['shopify.product.product.ept']
        shopify_products = self._context.get('active_ids', [])
        template = shopify_product_template_obj.browse(shopify_products)
        templates = template.filtered(lambda x: x.exported_in_shopify != True)
        if templates and len(templates) > 80:
            raise Warning("Error:\n- System will not export more then 80 Products at a "
                          "time.\n- Please select only 80 product for export.")

        if templates:
            shopify_product_obj.shopify_export_products(templates.shopify_instance_id,
                                                        self.shopify_is_set_price,
                                                        self.shopify_is_set_image,
                                                        self.shopify_is_publish,
                                                        self.shopify_is_set_basic_detail,
                                                        templates)
        end = time.time()
        _logger.info(
            "Export Processed %s Products in %s seconds." % (
                str(len(template)), str(end - start)))
        return True

    def manual_update_product_to_shopify(self):
        if not self.shopify_is_update_basic_detail and not self.shopify_is_publish and not self.shopify_is_set_price and not self.shopify_is_set_image:
            raise Warning("Please Select Any Option To Update Product")
        start = time.time()
        shopify_product_template_obj = self.env['shopify.product.template.ept']
        shopify_product_obj = self.env['shopify.product.product.ept']
        shopify_products = self._context.get('active_ids', [])
        template = shopify_product_template_obj.browse(shopify_products)
        templates = template.filtered(lambda x: x.exported_in_shopify)
        if templates and len(templates) > 80:
            raise Warning("Error:\n- System will not update more then 80 Products at a "
                          "time.\n- Please select only 80 product for export.")
        if templates:
            shopify_product_obj.update_products_in_shopify(templates.shopify_instance_id,
                                                           self.shopify_is_set_price,
                                                           self.shopify_is_set_image,
                                                           self.shopify_is_publish,
                                                           self.shopify_is_update_basic_detail,
                                                           templates)
        end = time.time()
        _logger.info(
            "Update Processed %s Products in %s seconds." % (
                str(len(template)), str(end - start)))
        return True

    def prepare_product_for_export_csv_file(self):
        """
        This method is used for export the odoo products in csv file format
        :param self: It contain the current class Instance
        :return:
        @author: Nilesh Parmar @Emipro Technologies Pvt. Ltd on date 04/11/2019
        """

        buffer = StringIO()
        active_template_ids = self._context.get('active_ids', [])
        template_ids = self.env['product.template'].browse(active_template_ids)
        # odoo_templates = self.env['product.template'].search(
        #         [('id', 'in', template_ids), ('default_code', '!=', False),
        #          ('type', '=', 'product')])
        # if not odoo_templates:
        #     raise Warning("Internel Reference (SKU) not set in selected products")
        odoo_template_ids = template_ids.filtered(lambda template: template.type == 'product')
        if not odoo_template_ids:
            raise Warning(_('It seems like selected products are not Storable Products.'))
        delimiter = ','
        field_names = ['template_name', 'product_name', 'product_default_code',
                       'product_description',
                       'PRODUCT_TEMPLATE_ID', 'PRODUCT_ID', 'CATEGORY_ID']
        csvwriter = DictWriter(buffer, field_names, delimiter=delimiter)
        csvwriter.writer.writerow(field_names)
        rows = []
        for odoo_template in odoo_template_ids:
            if len(odoo_template.attribute_line_ids) > 3:
                continue
            if len(odoo_template.product_variant_ids.ids) == 1 and not odoo_template.default_code:
                continue
            # if not odoo_template.default_code and not odoo_template.product_variant_ids:
            #     continue
            for product in odoo_template.product_variant_ids.filtered(
                    lambda variant: variant.default_code != False):
                row = {'PRODUCT_TEMPLATE_ID': odoo_template.id,
                       'template_name': odoo_template.name,
                       'CATEGORY_ID': odoo_template.categ_id.id,
                       'product_default_code': product.default_code,
                       'PRODUCT_ID': product.id,
                       'product_name': product.name,
                       'product_description': product.description or None,
                       }
                rows.append(row)
                # csvwriter.writerow(row)
        if not rows:
            raise Warning(_('No data found to be exported.\n\nPossible Reasons:\n   - Number of '
                            'attributes are '
                            'more than 3.\n   - SKU(s) are not set properly.'))
        csvwriter.writerows(rows)
        buffer.seek(0)
        file_data = buffer.read().encode()
        # if len(file_data) == 112:
        #     raise Warning(_("Selected products are not export in CSV file.\nPlease verify "
        #                     "products internal reference and "))
        self.write({
            'datas': base64.encodestring(file_data),
            'file_name': 'Shopify_export_product'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=shopify.process.import.export&id=%s&field=datas&field=datas&download=true&filename=%s.csv" % (
                self.id, self.file_name + str(datetime.now().strftime("%d/%m/%Y:%H:%M:%S"))),
            'target': self
        }

    def import_product_from_csv(self):
        """
        This method used to import product using csv file in shopify third layer
        images related changes taken by Maulik Barad
        @param : self
        @author: Nilesh Parmar @Emipro Technologies Pvt. Ltd on date 05/11/2019
        :return:
        """
        shopify_product_template = self.env['shopify.product.template.ept']
        shopify_product_obj = self.env['shopify.product.product.ept']
        common_log_obj = self.env["common.log.book.ept"]
        shopify_product_image_obj = self.env['shopify.product.image.ept']
        common_log_line_obj = self.env["common.log.lines.ept"]
        model_id = common_log_line_obj.get_model_id("shopify.process.import.export")

        if not self.choose_file:
            raise ValidationError("File Not Found To Import")
        if not self.file_name.endswith('.csv'):
            raise ValidationError("Please Provide Only .csv File To Import Product !!!")
        file_data = self.read_file()
        log_book_id = common_log_obj.create({'type': 'export',
                                             'module': 'shopify_ept',
                                             'shopify_instance_id': self.shopify_instance_id.id,
                                             'active': True})
        required_field = ['template_name', 'product_name', 'product_default_code',
                          'product_description', 'PRODUCT_TEMPLATE_ID', 'PRODUCT_ID', 'CATEGORY_ID']
        for required_field in required_field:
            if not required_field in file_data.fieldnames:
                raise Warning("Required Column Is Not Available In File")
        sequence = 0
        row_no = 1
        shopify_template_id = False
        for record in file_data:
            message = ""
            if not record['PRODUCT_TEMPLATE_ID'] or not record['PRODUCT_ID'] or not record[
                'CATEGORY_ID']:
                message += "PRODUCT_TEMPLATE_ID Or PRODUCT_ID Or CATEGORY_ID Not As Per Odoo Product %s" % (
                    row_no)
                vals = {'message': message,
                        'model_id': model_id,
                        'log_line_id': log_book_id.id,
                        }
                common_log_line_obj.create(vals)
                continue
            shopify_template = shopify_product_template.search(
                [('shopify_instance_id', '=', self.shopify_instance_id.id),
                 ('product_tmpl_id', '=', int(record['PRODUCT_TEMPLATE_ID']))])

            if not shopify_template:
                shopify_product_template_vals = (
                    {'product_tmpl_id': int(record['PRODUCT_TEMPLATE_ID']),
                     'shopify_instance_id': self.shopify_instance_id.id,
                     'shopify_product_category': int(record['CATEGORY_ID']),
                     'name': record['template_name'],
                     'description': record['product_description']
                     })
                shopify_template = shopify_product_template.create(shopify_product_template_vals)
                sequence = 1
                shopify_template_id = shopify_template.id

            else:
                if shopify_template_id != shopify_template.id:
                    shopify_product_template_vals = (
                        {'product_tmpl_id': int(record['PRODUCT_TEMPLATE_ID']),
                         'shopify_instance_id': self.shopify_instance_id.id,
                         'shopify_product_category': int(record['CATEGORY_ID']),
                         'name': record['template_name'],
                         'description': record['product_description']
                         })
                    shopify_template.write(shopify_product_template_vals)
                    shopify_template_id = shopify_template.id

            # For adding all odoo images into shopify layer.
            # if shopify_template_id != shopify_template.id:
            shoify_product_image_list = []
            product_template = shopify_template.product_tmpl_id
            for odoo_image in product_template.ept_image_ids.filtered(lambda x: not x.product_id):
                shopify_product_image = shopify_product_image_obj.search_read(
                    [("shopify_template_id", "=", shopify_template_id),
                     ("odoo_image_id", "=", odoo_image.id)], ["id"])
                if not shopify_product_image:
                    shoify_product_image_list.append({
                        "odoo_image_id": odoo_image.id,
                        "shopify_template_id": shopify_template_id
                    })
            if shoify_product_image_list:
                shopify_product_image_obj.create(shoify_product_image_list)

            if shopify_template and shopify_template.shopify_product_ids and \
                    shopify_template.shopify_product_ids[
                        0].sequence:
                sequence += 1
            shopify_variant = shopify_product_obj.search(
                [('shopify_instance_id', '=', self.shopify_instance_id.id), (
                    'product_id', '=', int(record['PRODUCT_ID'])),
                 ('shopify_template_id', '=', shopify_template.id)])
            if not shopify_variant:
                shopify_variant_vals = ({'shopify_instance_id': self.shopify_instance_id.id,
                                         'product_id': int(record['PRODUCT_ID']),
                                         'shopify_template_id': shopify_template.id,
                                         'default_code': record['product_default_code'],
                                         'name': record['product_name'],
                                         'sequence': sequence
                                         })
                shopify_variant = shopify_product_obj.create(shopify_variant_vals)
            else:
                shopify_variant_vals = ({'shopify_instance_id': self.shopify_instance_id.id,
                                         'product_id': int(record['PRODUCT_ID']),
                                         'shopify_template_id': shopify_template.id,
                                         'default_code': record['product_default_code'],
                                         'name': record['product_name'],
                                         'sequence': sequence
                                         })
                shopify_variant.write(shopify_variant_vals)
            row_no = +1
            # For adding all odoo images into shopify layer.
            product_id = shopify_variant.product_id
            odoo_image = product_id.ept_image_ids
            if odoo_image:
                shopify_product_image = shopify_product_image_obj.search_read(
                    [("shopify_template_id", "=", shopify_template_id),
                     ("shopify_variant_id", "=", shopify_variant.id),
                     ("odoo_image_id", "=", odoo_image[0].id)], ["id"])
                if not shopify_product_image:
                    shopify_product_image_obj.create({
                        "odoo_image_id": odoo_image[0].id,
                        "shopify_variant_id": shopify_variant.id,
                        "shopify_template_id": shopify_template_id,
                    })
        if not log_book_id.log_lines:
            log_book_id.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def read_file(self):
        """
            Read selected .csv file
            @author: Nilesh Parmar @Emipro Technologies Pvt. Ltd on date 08/11/2019
            :return:
        """
        self.write({'datas': self.choose_file})
        self._cr.commit()
        import_file = BytesIO(base64.decodestring(self.datas))
        file_read = StringIO(import_file.read().decode())
        reader = csv.DictReader(file_read, delimiter=',')
        return reader

    def shopify_export_variant_vals(self, instance, variant, shopify_template):
        """This method used prepare a shopify template vals for export product process,
            @param : self
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 17/10/2019.
        """
        shopify_variant_vals = {
            'shopify_instance_id': instance.id,
            'product_id': variant.id,
            'shopify_template_id': shopify_template.id,
            'default_code': variant.default_code,
            'name': variant.name,
        }
        return shopify_variant_vals

    def shopify_export_template_vals(self, instance, odoo_template):
        """This method used prepare a shopify template vals for export product process,
            @param : self
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 17/10/2019.
        """
        shopify_template_vals = {
            'shopify_instance_id': instance.id,
            'product_tmpl_id': odoo_template.id,
            'name': odoo_template.name,
            'description': odoo_template.description_sale,
            'shopify_product_category': odoo_template.categ_id.id,
        }
        return shopify_template_vals

    ######################## Below methods created by Angel Patel ########################

    def sync_shopify_customers(self):
        """This method used to sync the customers data from Shopify to Odoo.
            @param : self
            @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 23/10/2019.
            :Task ID: 157065
        """
        self.shopify_instance_id.connect_in_shopify()
        if not self.shopify_instance_id.shopify_last_date_customer_import:
            customer_ids = shopify.Customer().search(limit=200)
            _logger.info("Imported first 200 Customers.")
            if len(customer_ids) >= 200:
                customer_ids = self.shopify_list_all_customer(customer_ids)
        else:
            customer_ids = shopify.Customer().find(
                updated_at_min=self.shopify_instance_id.shopify_last_date_customer_import)
            if len(customer_ids) >= 200:
                customer_ids = self.shopify_list_all_customer(customer_ids)
        if customer_ids:
            self.shopify_instance_id.shopify_last_date_customer_import = datetime.now()
        if not customer_ids:
            _logger.info(
                'Customers not found in result while the import customers from Shopify')
            return False
        _logger.info('Synced Customers len {}'.format(len(customer_ids)))
        # vals = {
        #     'shopify_instance_id': self.shopify_instance_id and self.shopify_instance_id.id or False,
        #     'state': 'draft',
        #     'record_created_from': 'import_process'
        # }
        customer_queue_list = []
        data_queue = self.env['shopify.customer.data.queue.ept']

        if len(customer_ids) > 0:
            # vals.update({'total_record_count': len(customer_ids)})

            if len(customer_ids) > 150:
                for customer_id_chunk in split_every(150, customer_ids):
                    customer_queue_id = data_queue.shopify_create_customer_queue(self.shopify_instance_id, "import_process")
                    customer_queue = self.shopify_create_multi_queue(customer_queue_id, customer_id_chunk)
                    customer_queue_list.append(customer_queue.id)
            else:
                customer_queue_id = data_queue.shopify_create_customer_queue(self.shopify_instance_id, "import_process")
                customer_queue = self.shopify_create_multi_queue(customer_queue_id, customer_ids)
                customer_queue_list.append(customer_queue.id)
        return customer_queue_list

    def shopify_create_multi_queue(self, customer_queue_id, customer_ids):
        """Create customer queue and queue line as per the requirement.
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 23/10/2019.
        :Task ID: 157065
        :param customer_queue_id:
        :param customer_ids:
        :return: True
        Modify Haresh Mori on date 26/12/2019 modification is changing the variable name.
        """
        # synced_shopify_customers_data_obj = self.env['shopify.customer.data.queue.ept']
        # synced_shopify_customers_line_obj = self.env['shopify.customer.data.queue.line.ept']
        # customer_queue_id = synced_shopify_customers_data_obj.create(vals)
        # customer_queue_id = self.shopify_customer_data_queue_create(vals)
        if customer_queue_id:
            for result in customer_ids:
                result = result.to_dict()
                self.shopify_customer_data_queue_line_create(result, customer_queue_id)
                # id = result.get('id')
                # name = "%s %s" % (result.get('first_name') or '', result.get('last_name') or '')
                # data = json.dumps(result)
                # line_vals = {
                #     'synced_customer_queue_id':customer_queue_id.id,
                #     'shopify_customer_data_id':id or '',
                #     'state':'draft',
                #     'name':name.strip(),
                #     'shopify_synced_customer_data':data,
                #     'shopify_instance_id':self.shopify_instance_id.id,
                #     'last_process_date':datetime.now(),
                # }
                # synced_shopify_customers_line_obj.create(line_vals)
        return customer_queue_id

    def shopify_customer_data_queue_line_create(self, result, customer_queue_id):
        """
        This method is used for create customer queue line using the result param and customer_queue_id.
        :param result:
        :param customer_queue_id:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 13/01/2020.
        """
        synced_shopify_customers_line_obj = self.env['shopify.customer.data.queue.line.ept']
        id = result.get('id')
        name = "%s %s" % (result.get('first_name') or '', result.get('last_name') or '')
        data = json.dumps(result)
        line_vals = {
            'synced_customer_queue_id': customer_queue_id.id,
            'shopify_customer_data_id': id or '',
            'state': 'draft',
            'name': name.strip(),
            'shopify_synced_customer_data': data,
            'shopify_instance_id': self.shopify_instance_id.id,
            'last_process_date': datetime.now(),
        }
        synced_shopify_customers_line_obj.create(line_vals)

    def webhook_customer_create_process(self, res, instance):
        """
        This method is used for create customer queue and queue line while the customer create form the webhook method.
        :param res:
        :param instance:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 13/01/2020.
        """
        res_partner_ept = self.env['shopify.res.partner.ept']
        data_queue = self.env['shopify.customer.data.queue.ept']
        customer_queue_id = data_queue.shopify_create_customer_queue(instance, "webhook")
        self.shopify_customer_data_queue_line_create(res, customer_queue_id)
        _logger.info(
            "process end : shopify odoo webhook for customer route call and customer queue is %s" % customer_queue_id.name)
        customer_queue_id.synced_customer_queue_line_ids.sync_shopify_customer_into_odoo()
        res_partner_obj = res_partner_ept.search([('shopify_customer_id', '=', res.get('id'))], limit=1)
        res_partner_obj.partner_id.update({
            'type': 'invoice'
        })

    def shopify_list_all_customer(self, result):
        """
            This method used to call the page wise data import for customers from Shopify to Odoo.
            @param : self,result
            @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 14/10/2019.
            :Task ID: 157065
            Modify by Haresh Mori on date 26/12/2019, Taken Changes for the pagination and API version.
        """
        sum_cust_list = []
        catch = ""
        while result:
            page_info = ""
            sum_cust_list += result
            link = shopify.ShopifyResource.connection.response.headers.get('Link')
            if not link or not isinstance(link, str):
                return sum_cust_list
            for page_link in link.split(','):
                if page_link.find('next') > 0:
                    page_info = page_link.split(';')[0].strip('<>').split('page_info=')[1]
                    try:
                        result = shopify.Customer().find(page_info=page_info, limit=200)
                        _logger.info("Imported next 200 Customers.")
                    except Exception as e:
                        if e.response.code == 429 and e.response.msg == "Too Many Requests":
                            time.sleep(5)
                            result = shopify.Customer().find(page_info=page_info, limit=200)
                        else:
                            raise Warning(e)
            if catch == page_info:
                break
        return sum_cust_list

    @api.model
    def update_stock_in_shopify(self, ctx={}):
        """
            This method used to export inventory stock from odoo to shopify.
            @param : self
            @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 09/11/2019.
            :Task ID: 157407
        :return:
        """
        if self.shopify_instance_id:
            instance = self.shopify_instance_id
        elif ctx.get('shopify_instance_id'):
            instance_id = ctx.get('shopify_instance_id')
            instance = self.env['shopify.instance.ept'].browse(instance_id)

        product_obj = self.env['product.product']
        shopify_product_obj = self.env['shopify.product.product.ept']
        last_update_date = instance.shopify_last_date_update_stock
        if not last_update_date:
            last_update_date = datetime.now() - timedelta(30)

        products = product_obj.get_products_based_on_movement_date(last_update_date,
                                                                   instance.shopify_company_id)
        if products:
            product_id_array = sorted(list(map(lambda x: x['product_id'], products)))
            product_id_array and shopify_product_obj.export_stock_in_shopify(instance,
                                                                             product_id_array)
        return True

    def shopify_selective_product_stock_export(self):
        shopify_product_template_ids = self._context.get('active_ids')
        shopify_instance_ids = self.env['shopify.instance.ept'].search([])
        for instance_id in shopify_instance_ids:
            product_id = self.env['shopify.product.product.ept'].search(
                [('shopify_instance_id', '=', instance_id.id),
                 ('shopify_template_id', 'in', shopify_product_template_ids)]).product_id.ids
            if product_id:
                self.env['shopify.product.product.ept'].export_stock_in_shopify(instance_id,
                                                                                product_id)

    def import_stock_in_odoo(self):
        """
        Import stock from shopify to odoo
        import_shopify_stock method write in shopify_product_ept.py file
        :return: 157905
        """
        instance = self.shopify_instance_id
        shopify_product_obj = self.env['shopify.product.product.ept']
        shopify_product_obj.import_shopify_stock(instance)

    def update_order_status_in_shopify(self, instance=False):
        """
        Update order status function call from here
        update_order_status_in_shopify method write in sale_order.py
        :param instance:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt.
        :Task ID: 157905
        """
        if not instance:
            instance = self.shopify_instance_id
        if instance.active:
            _logger.info(_("Your current active instance is '%s'") % instance.name)
            self.env['sale.order'].update_order_status_in_shopify(instance)
        else:
            _logger.info(_("Your current instance '%s' is in active.") % instance.name)

    def update_order_status_cron_action(self, ctx={}):
        """
        Using cron update order status
        :param ctx:
        :return:
        @author: Angel Patel @Emipro Technologies Pvt.
        :Task ID: 157716
        """
        instance_id = ctx.get('shopify_instance_id')
        instance = self.env['shopify.instance.ept'].browse(instance_id)
        _logger.info(
            _(
                "Auto cron update order status process start with instance: '%s'") % instance.name)
        self.update_order_status_in_shopify(instance)

    @api.onchange("shopify_instance_id")
    def onchange_shopify_order_date(self):
        """
        Author: Bhavesh Jadav 23/12/2019 for set fom date  instance wise
        :return:
        """
        instance = self.shopify_instance_id or False
        if instance:
            self.orders_from_date = instance.last_date_order_import or False
            self.orders_to_date = datetime.now()
