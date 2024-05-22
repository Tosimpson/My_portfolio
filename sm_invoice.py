from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
import logging
import base64

_logger = logging.getLogger(__name__)


class SchoolInvoice(models.Model):
    _name = 'sm.invoice'
    _description = 'School Invoice'
    # _inherit = 'ir.actions.report'

    student_id = fields.Many2many('sm.student', string='Student', required=True)
    invoice_number = fields.Char(string='Invoice Number', default=lambda self: self._generate_invoice_number(), 
        readonly=True)
    date = fields.Date(string='Invoice Date', required=True, default=fields.Date.today)
    due_date = fields.Date(string='Due Date', required=True)
    amount = fields.Float(string='Invoice Amount', required=True)
    is_paid = fields.Boolean(string='Is Paid', default=False)
    invoice_template = fields.Many2one('sm.invoice.template', string='Invoice Template', domain="[('state', '!=', 'draft')]", required=True)
    invoice_items = fields.Many2many('sm.invoice.item', string='Template Items', compute='_compute_invoice_items', readonly=True, store=True )

    contact_email = fields.Char(related='student_id.contact_email', string='Contact Email', store=True)
    name = fields.Char(related='invoice_template.name', string='Name', store=True)
    combination = fields.Char(string='Combination', compute='_compute_fields_combination')

    @api.depends('student_id', 'invoice_template')
    def _compute_fields_combination(self):
        for s in self:
            combination = f"{s.student_id.name}-{s.invoice_template.name}" if s.invoice_template else s.student_id.name
            s.combination = combination

    @api.onchange('invoice_template')
    def _onchange_invoice_template(self):
        if self.invoice_template:
            self.amount = self.invoice_template.total

    @api.depends('invoice_template')
    def _compute_invoice_items(self):
        for record in self:
            if record.invoice_template:
                record.invoice_items = record.invoice_template.invoice_items.ids
                _logger.info("Invoice items: %s", record.invoice_items)

    @api.constrains('due_date')
    def _check_due_date(self):
        for record in self:
            if record.due_date < record.date:
                raise ValidationError("Due date cannot be less than the invoice date.")
            
    # @api.model
    # def create(self, vals):
    #     if 'due_date' in vals and 'date' in vals and vals['due_date'] < vals['date']:
    #         raise ValidationError("Due date cannot be less than the invoice date.")
    #     return super(SchoolInvoice, self).create(vals)

    @api.model
    def create(self, vals):
        # Extract student IDs from the vals dictionary
        student_ids = vals.pop('student_id', [])

        # Create invoice records for each student
        for student_id in student_ids[0][2]:  # Corrected line
            # Create a copy of the original dictionary to avoid modifying it
            invoice_vals = vals.copy()
            
            # Add the current student ID to the invoice values
            invoice_vals['student_id'] = [(6, 0, [student_id])]
            
            # Create the invoice record
            invoice = super(SchoolInvoice, self).create(invoice_vals)

            # Call the action_send_invoice_email method on the new record
            # only if the 'no_email' context value is not set
            if not self.env.context.get('no_email'):
                invoice.action_send_invoice_email()

        return invoice  # Return the last invoice created

    # @api.model
    # def create(self, vals):
    #     if 'due_date' in vals and 'date' in vals and vals['due_date'] < vals['date']:
    #         raise ValidationError("Due date cannot be less than the invoice date.")
    #     return super(SchoolInvoice, self).create(vals)

    def write(self, vals):
        if 'due_date' in vals and 'date' in self and vals['due_date'] < self.date:
            raise ValidationError("Due date cannot be less than the invoice date.")
        return super(SchoolInvoice, self).write(vals)
    
    def _generate_invoice_number(self):
        sequence = self.env['ir.sequence'].next_by_code('sm.school.invoice') or '/'
        return sequence
    
    @api.model
    def action_send_invoice_email(self):
        self.ensure_one()
        template = self.env.ref('school_management.email_template_invoice')  # replace with your module name
        report = self.env.ref('school_management.invoice_report')  # replace with your module name
        # Render the PDF
        pdf_content, content_type = report.render_qweb_pdf(self.ids)
        # Create a new attachment
        attachment = self.env['ir.attachment'].create({
            'name': 'Invoice.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
        })
        # Add the PDF attachment to the email template
        template.attachment_ids = [(4, attachment.id)]
        # Send the email
        template.send_mail(self.id)

    # @api.model
    # def render_qweb_pdf(self, docids, data=None):
    #     docs = self.env['sm.invoice'].browse(docids)
    #     report = self.env['ir.actions.report']._get_report_from_name('school_management.invoice_report')
    #     return report.render(docids, data=data)
    
    # def generate_invoice_report(self, invoice_id):
    #     invoice = self.browse(invoice_id)
    #     if not invoice:
    #         raise UserError(_("Invoice not found."))

    #     # Retrieve the invoice report template
    #     report_template = self.env.ref('school_management.invoice_report')
    #     print(report_template)

    #     # Check if the report template exists and supports render_qweb_pdf
    #     if not report_template or not hasattr(report_template, 'render_qweb_pdf'):
    #         raise UserError(_("Invalid report template or missing render_qweb_pdf method."))

    #     # Generate the PDF report
    #     report = report_template.render_qweb_pdf([invoice.id])
    #     print(report)
    #     if not report:
    #         raise UserError(_("Failed to generate invoice report."))

    #     return report
    
    # def generate_invoice_report(self, invoice_id):
    #     invoice = self.browse(invoice_id)
    #     if not invoice.invoice_template:
    #         raise UserError(_("Please select an invoice template."))

    #     # Render the invoice report template
    #     report = self.env.ref('school_management.invoice_report').render(invoice.ids)[0]

    #     return report

    # def generate_invoice_report(self, invoice_id):
    #     invoice = self.browse(invoice_id)
    #     if not invoice:
    #         raise UserError(_("Invoice not found."))

    #     # Call the report action to generate the PDF report
    #     action = self.env.ref('school_management.action_invoice_report_pdf')
    #     report = action.report_action([invoice.id])

    #     if not report:
    #         raise UserError(_("Failed to generate invoice report."))

    #     return report
    
    # def send_invoice_email(self, invoice_id):
    #     invoice = self.browse(invoice_id)
    #     if not invoice.contact_email:
    #         raise UserError(_("The invoice does not have a contact email."))

    #     # Generate the invoice report
    #     report = self.generate_invoice_report(invoice_id)

    #     if not report:
    #         raise UserError(_("Failed to generate invoice report."))
        
    #     # Encode the report data using base64
    #     report_data = base64.b64encode(report)

    #     # Attach the report to the email
    #     attachments = [(invoice.invoice_number + '.pdf', report)]

    #     # Customize email content
    #     subject = "Invoice: {}".format(invoice.invoice_template.name)
    #     body = "Dear esteemed parent,\n\nPlease find attached the {} for your reference.\n\nBest regards,\n[Your Company]".format(subject)

    #     # Send email with attachment
    #     mail_values = {
    #         'subject': subject,
    #         'body_html': body,
    #         'email_to': invoice.contact_email,
    #         'attachment_ids': [(0, 0, {
    #             'name': attachments[0][0],
    #             'datas': report_data,
    #             'datas_fname': attachments[0][0]
    #         })],
    #     }
    #     self.env['mail.mail'].create(mail_values).send()

    # def action_send_invoice_email(self):
    #     for invoice in self:
    #         self.send_invoice_email(invoice.id)