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

from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning, RedirectWarning
import tempfile
import re
import werkzeug
from urlparse import urljoin
from openerp.tools import html2plaintext

from reportlab.lib import colors
from reportlab.lib.pagesizes import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4, landscape


class account_invoice(models.Model):
    _inherit = "account.invoice"

    @api.model
    def _query_report(self, user_id=None, state='open', date_interval='6 months'):
        operator = 'is NULL' if user_id is None else '='
        user_id = '' if user_id is None else user_id
        select_field = 'ai.id as id, ' \
                       'ai.nextdate_payment_commitment as nextdate_payment, ' \
                       'rp.name as name, ' \
                       'rp.fiscal_name as business_name, ' \
                       'ai.number as invoice_number, ' \
                       'ai.date_due as date_due, ' \
                       'rc.name as currency_name, ' \
                       'rc.symbol as currency_symbol, ' \
                       'ai.amount_total as amount'
        from_table = 'account_invoice ai, res_partner rp, res_currency rc'
        where_field = 'ai.partner_id = rp.id AND ' \
                      'ai.currency_id = rc.id AND ' \
                      'rp.user_id %s%s AND ' \
                      'ai.state = \'%s\' AND ' \
                      'ai.date_due < CURRENT_DATE AND ' \
                      'ai.date_due > CURRENT_DATE - INTERVAL \'%s\'' % (operator, user_id, state, date_interval)
        order_field = 'ai.date_due DESC'

        self.env.cr.execute('SELECT %s FROM %s WHERE %s ORDER BY %s' % (select_field, from_table,
                                                                        where_field, order_field))
        res = self.env.cr.dictfetchall()
        return res

    def generate_week_report(self, cr, uid):
        user_ids = self._get_user(cr, uid, group1=True)
        if user_ids:
            for user in user_ids:
                res = self._query_report(cr, uid, user_id=user.id)
                if res:
                    email = user.email if self.validate_email(user.email) else None
                    # CONTENT
                    styles = getSampleStyleSheet()
                    elements = []
                    title = u'Reporte Semanal de Cobranza'
                    style_h_one = styles['Heading1']
                    elements.append(Paragraph(title, style_h_one))
                    elements.append(Spacer(1, 0.25 * inch))

                    # PDF
                    pdfreport_fd, pdfreport_path = tempfile.mkstemp(suffix='.pdf', prefix='reporte.cobranza.')
                    body_html = 'Hola <b>%s</b>, <p>Se adjunta el reporte de cobranza de la semana.</p>' % user.name
                    doc = SimpleDocTemplate(pdfreport_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30,
                                            bottomMargin=18)
                    doc.pagesize = landscape(A4)
                    doc.build(self._report_table(cr, uid, res, elements))
                    attachments = [[title, pdfreport_path]]
                    # EMAIL
                    self.send_mail(cr, uid, attachments=attachments, email_to=email, subject=title,
                                   html=body_html, force_send=True)
        return True

    def generate_consolidated_week_report(self, cr, uid):
        parent_user_ids = self._get_user(cr, uid, group2=True)
        if parent_user_ids:
            for manager in parent_user_ids:
                email = manager.email if self.validate_email(manager.email) else None
                # CONTENIDO DE REPORTE
                styles = getSampleStyleSheet()
                elements = []
                title = u'Reporte Semanal de Cobranza Consolidado'
                style_h_one = styles['Heading1']
                elements.append(Paragraph(title, style_h_one))
                elements.append(Spacer(1, 0.25 * inch))
                # facturas por ejecutivas
                user_ids = self._get_user(cr, uid, group1=True)
                for user in user_ids:
                    res = self._query_report(cr, uid, user_id=user.id)
                    elements = self._report_table(cr, uid, res, elements, title=user.name)
                # facturas sin ejecutivas
                res = self._query_report(cr, uid)
                elements = self._report_table(cr, uid, res, elements, title=u'Sin ejecutiva responsable')

                # PDF
                pdfreport_fd, pdfreport_path = tempfile.mkstemp(suffix='.pdf', prefix='reporte.cobranza.consol.')
                body_html = 'Hola <b>%s</b>, <p>Se adjunta el reporte semanal de cobranza consolidado.</p>' % manager.name
                doc = SimpleDocTemplate(pdfreport_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30,
                                        bottomMargin=18)
                doc.pagesize = landscape(A4)
                doc.build(elements)
                attachments = [[title, pdfreport_path]]
                # EMAIL
                self.send_mail(cr, uid, attachments=attachments, email_to=email, subject=title,
                               html=body_html, force_send=True)
        return True

    @api.model
    def _report_table(self, res, elements, title=None):
        elements = elements if elements else []
        if res:
            data = []
            styles = getSampleStyleSheet()
            data_header = [u'Empresa', u'Nro factura', u'Fecha de Vencimiento', u'Total + IGV', u'Prox. Pago',
                           u'Comentarios']
            data.append(data_header)

            for r in res:
                invoice_number = Paragraph('''<a href="%s" color="blue">%s</a>''' % (self.invoice_url(r.get('id')),
                                                                                     r.get('invoice_number')),
                                           styles["BodyText"])

                name = r.get('name').encode('utf-8') if r.get('name') else ''
                name = (name[:42] + '..') if len(name) > 42 else name
                business_name = r.get('business_name').encode('utf-8') if r.get('business_name') else ''
                business_name = (business_name[:42] + '..') if len(business_name) > 42 else business_name
                company = name + '\n' + business_name
                amount = str(r.get('currency_symbol')) + str(r.get('amount'))
                data_content = [company, invoice_number, r.get('date_due'), amount, r.get('nextdate_payment'),
                                self._invoice_messages(r.get('id'))]

                data.append(data_content)

            # style content
            if title:
                style_h_for = styles['Heading4']
                elements.append(Paragraph(title, style_h_for))
                elements.append(Spacer(1, 0.25 * inch))
            t = Table(data, colWidths=[3.2 * inch, None, None, None, None, 3.3 * inch])
            t.setStyle(TableStyle([('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                   ('FONTSIZE', (0, 0), (-1, -1), 8),
                                   ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                                   ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                                   ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                   ('INNERGRID', (0, 0), (-1, -1), 0.50, colors.black),
                                   ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
                                   ]))
            elements.append(t)

        return elements

    @api.model
    def _get_user(self, group1=False, group2=False):
        # USER ROLE
        user_ids = []
        if group1: 
            groups_id = self.env['res.groups'].search([('name', '=', 'Ejecutiva de Venta')], limit=1)
            user_ids = self.env['res.users'].search([('groups_id', '=', groups_id.id)])
        elif group2:
            groups_id = self.env['res.groups'].search([('name', 'in', ['Jefe de Ventas', 'Jefe de Facturación'])])
            ids = list(map(lambda g: g.id, groups_id))
            user_ids = self.env['res.users'].search([('groups_id', 'in', ids)])
        return user_ids

    @api.cr_uid_id_context
    def send_mail(self, cr, uid, attachments, email_to=None, subject=None, html=None, force_send=False,
                  raise_exception=False, context=None):
        """Generates a new mail message for the given template and record,
           and schedules it for delivery through the ``mail`` module's scheduler.

           :param attachments: file PDF
           :param string email_to: if is None, not send email
           :param string subject: subject for email
           :param string html: if is not None, send content email
           :param bool force_send: if True, the generated mail.message is
                immediately sent after being created, as if the scheduler
                was executed for this message only.
           :returns: id of the mail.message that was created
        """
        if context is None:
            context = {}
        mail_mail = self.pool.get('mail.mail')
        ir_attachment = self.pool.get('ir.attachment')

        email_to = 'murpol.20@gmail.com' if email_to is None else email_to
        subject = 'sin asunto' if subject is None else subject
        html = '.' if html is None else html

        # create a mail_mail based on values, without attachments
        values = {
            'subject': subject,
            'body_html': html,
            'email_from': 'admin@company.com',
            'email_to': email_to,
            'partner_to': '',
            'email_cc': '',
            'reply_to': ''
        }
        msg_id = mail_mail.create(cr, uid, values, context=context)
        mail = mail_mail.browse(cr, uid, msg_id, context=context)

        attachment_ids = []
        # manage attachments
        for attachment in attachments:
            with open(attachment[1], 'r') as fp:
                content = fp.read().encode('base64')
            attachment_data = {
                'name': attachment[0],
                'datas_fname': attachment[1].split('/')[2],
                'datas': content,
                'res_model': 'mail.message',
                'type': 'binary',
                'res_id': mail.mail_message_id.id,
            }
            context = dict(context)
            context.pop('default_type', None)
            attachment_ids.append(ir_attachment.create(cr, uid, attachment_data, context=context))
        if attachment_ids:
            values['attachment_ids'] = [(6, 0, attachment_ids)]
            mail_mail.write(cr, uid, msg_id, {'attachment_ids': [(6, 0, attachment_ids)]}, context=context)

        if force_send:
            mail_mail.send(cr, uid, [msg_id], raise_exception=raise_exception, context=context)
        return msg_id

    @api.model
    def _invoice_messages(self, res_id):
        styles = getSampleStyleSheet()
        msg_invoice = []
        domain_where = [('model', '=', 'account.invoice'), ('type', '=', 'comment'),
                        ('res_id', '=', res_id)]
        messages = self.env['mail.message'].search(domain_where, order='id DESC', limit=3)
        i = 0
        for msg in messages:
            content = (html2plaintext(msg.body) or "")
            i += 1
            p = Paragraph('''<para align=left spaceb=3><b>%s - </b>%s</para>''' % (i, content),
                          styles["BodyText"])
            msg_invoice.append(p)
        return msg_invoice

    @api.model
    def invoice_url(self, res_id):
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        fragment = dict()
        fragment['id'] = res_id
        fragment['model'] = 'account.invoice'
        fragment['view_type'] = 'form'
        query = '#' + werkzeug.url_encode(fragment)
        url = urljoin(base_url, "/web?%s" % query)

        return url

    def validate_email(self, email):
        validate = True
        if not email:
            return False
        if re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", email) == None:
            validate = False
        return validate
