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

from openerp import tools
from openerp.osv import fields,osv


class account_journal_report(osv.osv):
    _name = "account.journal.report"
    _description = "Account Journal Statistics"
    _auto = False
    _columns = {
        'date': fields.date('Date', readonly=True),
        'date_invoice': fields.date('Date Invoice', readonly=True),
        'name_partner': fields.char('Name Partner', readonly=True),
        'invoice_number': fields.char('Invoice Number', readonly=True),
        'number': fields.char('Number Operation', readonly=True),
        'doc_number': fields.char('Doc Number', readonly=True),
        'business_name': fields.char('Fiscal Name', readonly=True),
        'cuota': fields.char('Cuota', readonly=True),
        'name_journal': fields.char('Name Journal', readonly=True),
        'name_template': fields.char('Name Edition', readonly=True),
        'currency_symbol': fields.char('Currency Symbol', readonly=True),
        'amount': fields.float('Amount', readonly=True),
        'memory': fields.char('Description Memory', readonly=True),
        'nbr': fields.integer('# Lines', readonly=True),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True),
    }

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'account_journal_report')
        cr.execute("""
            create or replace view account_journal_report as (
                SELECT min(av.id) as id,
                    count(DISTINCT av.id) as nbr,
                    av.date as date,
                    ai.date_invoice as date_invoice,
                    rp.name as name_partner,
                    ai.number as invoice_number,
                    rp.doc_number as doc_number,
                    rp.fiscal_name as business_name,
                    (CASE WHEN solc.nro_cuota IS NOT NULL THEN 'Cuota ' || solc.nro_cuota
                      WHEN (TRIM(substr(ail.name, length(ail.name) - 12, 6))) = 'Cuota'
                        THEN (TRIM(substr(ail.name, length(ail.name) - 12, 8)))
                      ELSE ''
                      END) as cuota,
                    aj.name as name_journal,
                    pt.name as name_template,
                    rc.symbol as currency_symbol,
                    av.reference as number,
                    av.amount as amount,
                    av.name as memory,
                    av.partner_id as partner_id,
                    av.journal_id as journal_id,
                    ai.currency_id as currency_id
                FROM account_voucher av
                    LEFT JOIN res_partner rp ON (av.partner_id = rp.id)
                    LEFT JOIN account_journal aj ON (av.journal_id = aj.id)
                    LEFT JOIN account_voucher_line avl ON (av.id = avl.voucher_id)
                    LEFT JOIN account_move_line aml ON (avl.move_line_id = aml.id)
                    LEFT JOIN account_move am ON (aml.move_id = am.id)
                    LEFT JOIN account_invoice ai ON (am.name = ai.internal_number)
                    LEFT JOIN sale_order_line_cuota solc ON (ai.id = solc.invoice_id)
                    LEFT JOIN account_invoice_line ail ON (ai.id = ail.invoice_id)
                    LEFT JOIN product_product pp ON (ail.product_id = pp.id)
                    LEFT JOIN product_template pt ON (pp.product_tmpl_id = pt.id)
                    LEFT JOIN res_currency rc ON (ai.currency_id = rc.id)
                WHERE avl.reconcile = TRUE AND av.state='posted'
                GROUP BY av.date, ai.date_invoice, rp.name, ai.number, rp.doc_number, rp.fiscal_name,
                  solc.nro_cuota, ail.name, aml.date_maturity, aj.name, pt.name, rc.symbol, av.reference, av.amount,
                  av.name, av.partner_id, av.journal_id, ai.currency_id
            )
        """)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
