# -*- encoding: utf-8 -*-
######################################################################################
#
#    Odoo/OpenERP, Open Source Management Solution
#    Copyright (c) Jonathan Murga
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
######################################################################################

from openerp import fields, models, api, exceptions


class sale_order(models.Model):
    _inherit = "sale.order"

    supplier_id = fields.Many2one('res.partner', string="Supplier", domain=[('supplier', '=', True)])
    vehicle_id = fields.Many2one('fleet.vehicle', string="Vehicle", help="Vehicle by transport")
    driver_id = fields.Many2one('res.partner', string="Driver", domain=[('is_contact', '=', True)])
    date_execution = fields.Date(string="Fecha de ejecucion")

    star_date_transfer = fields.Date(string="Transfer On")
    starting_address = fields.Many2one('res.partner', string="Start Address")
    arrival_address = fields.Many2one('res.partner', string="Arrival Address")

    sender_name = fields.Many2one('res.partner', string="Sender Name")

    addressee_name = fields.Many2one('res.partner', string="Addressee Name")

    dangerous_goods = fields.Selection(string="Mercaderia Peligrosa", selection=[('si', 'Si'), ('no', 'No')])

    transfer = fields.Boolean(string="Transbordo")
    discontinued = fields.Boolean(string="Interrumpido")

    outsourced_name = fields.Many2one('res.partner', string="Outsourced Name")

    volume_capacity = fields.Float(string="Volumen (m3)")
    dist_virtual = fields.Float(string="Dist. Virtual (km)")

    @api.multi
    def write(self, values):
        if values.get('order_line'):
            volume_capacity = self._get_volume_capacity(values.get('order_line'))
            if volume_capacity:
                values.update({'volume_capacity': volume_capacity})
        rec = super(sale_order, self).write(values)
        return rec

    @api.model
    def create(self, values):
        if values.get('order_line'):
            volume_capacity = self._get_volume_capacity(values.get('order_line'))
            if volume_capacity:
                values.update({'volume_capacity': volume_capacity})
        rec = super(sale_order, self).create(values)
        return rec

    def _get_volume_capacity(self, order_line):
        total_weight = False
        f = lambda val: [dict(id=i[1], val=i[2]['weight']) for i in val if i[2] and i[2].get('weight')]
        data = f(order_line)
        if isinstance(data, list) and data:
            try:
                if self.id:
                    total_weight = 0
                    order_line_obj = self.env['sale.order.line'].search([('order_id', '=', self.id)])
                    for rec in order_line_obj:
                        f = lambda w, id: [i['val'] for i in w if i.get('id') == id or i.get('id') == False]
                        dw = f(data, rec.id)
                        weight = dw[0] if dw else rec.weight
                        total_weight = total_weight + weight
                else:
                    f = lambda w: sum([i['val'] for i in w])
                    total_weight = f(data)
            except:
                pass
        return total_weight

    def action_button_confirm(self, cr, uid, ids, context=None):
        for sale in self.browse(cr, uid, ids, context=None):
            if not sale.supplier_id or not sale.vehicle_id or not sale.driver_id:
                raise exceptions.ValidationError(
                    u"Tiene que elegir un proveedor, unidad y conductor para confirmar la venta")
        return super(sale_order, self).action_button_confirm(cr, uid, ids, context=context)

