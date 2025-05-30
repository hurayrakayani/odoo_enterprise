from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def write(self, vals):
        suspense_account = self.company_id.account_journal_suspense_account_id
        if (
            self.company_id.account_fiscal_country_id.code == 'BE'
            and 'account_id' in vals
            and self.account_id == suspense_account
        ):
            if mapping := self.env['soda.account.mapping'].search([
                ('company_id', '=', self.company_id.id),
                ('name', '=', self.name),
                '|',
                    ('account_id', '=', False),
                    ('account_id', '=', suspense_account.id),
            ]):
                mapping.account_id = vals['account_id']
        return super().write(vals)
