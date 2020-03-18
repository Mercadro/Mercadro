from odoo import models, fields, api, _

class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    # This field use to identify the Shopify delivery method
    shopify_code = fields.Char("Shopify Code")

    def shopify_search_create_delivery_carrier(self, line):
        delivery_method = line.get('title')
        carrier = False
        if delivery_method:
            carrier = self.search(
                    [('shopify_code', '=', delivery_method)], limit=1)
            if not carrier:
                carrier = self.search(
                        ['|', ('name', '=', delivery_method),
                         ('shopify_code', '=', delivery_method)], limit=1)
            if not carrier:
                carrier = self.search(
                        ['|', ('name', 'ilike', delivery_method),
                         ('shopify_code', 'ilike', delivery_method)], limit=1)
            if not carrier:
                product_template = self.env['product.template'].search(
                        [('name', '=', delivery_method), ('type', '=', 'service')], limit=1)
                if not product_template:
                    product_template = self.env['product.template'].create(
                            {'name':delivery_method, 'type':'service'})
                carrier = self.create(
                        {'name':delivery_method, 'shopify_code':delivery_method,
                         'product_id':product_template.product_variant_ids[0].id})
        return carrier
