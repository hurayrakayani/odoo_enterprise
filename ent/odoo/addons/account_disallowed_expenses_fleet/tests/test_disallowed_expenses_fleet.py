# -*- coding: utf-8 -*-

from freezegun import freeze_time
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

from odoo import Command, fields
from odoo.tests import tagged


@freeze_time('2022-07-15')
@tagged('post_install', '-at_install')
class TestAccountDisallowedExpensesFleetReport(TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.dna_category = cls.env['account.disallowed.expenses.category'].create({
            'code': '1234',
            'name': 'DNA category',
            'rate_ids': [
                Command.create({
                    'date_from': fields.Date.from_string('2022-01-01'),
                    'rate': 60.0,
                    'company_id': cls.company_data['company'].id,
                }),
                Command.create({
                    'date_from': fields.Date.from_string('2022-04-01'),
                    'rate': 40.0,
                    'company_id': cls.company_data['company'].id,
                }),
                Command.create({
                    'date_from': fields.Date.from_string('2022-08-01'),
                    'rate': 23.0,
                    'company_id': cls.company_data['company'].id,
                }),
            ],
        })

        cls.company_data['default_account_expense'].disallowed_expenses_category_id = cls.dna_category.id
        cls.company_data['default_account_expense_2'] = cls.company_data['default_account_expense'].copy()
        cls.company_data['default_account_expense_2'].disallowed_expenses_category_id = cls.dna_category.id

        cls.batmobile, cls.batpod = cls.env['fleet.vehicle'].create([
            {
                'model_id': cls.env['fleet.vehicle.model'].create({
                    'name': name,
                    'brand_id': cls.env['fleet.vehicle.model.brand'].create({
                        'name': 'Wayne Enterprises',
                    }).id,
                    'vehicle_type': vehicle_type,
                    'default_fuel_type': 'hydrogen',
                }).id,
                'rate_ids': [Command.create({
                    'date_from': fields.Date.from_string('2022-01-01'),
                    'rate': rate,
                })],
            } for name, vehicle_type, rate in [('Batmobile', 'car', 31.0), ('Batpod', 'bike', 56.0)]
        ])

        cls.env['fleet.disallowed.expenses.rate'].create({
            'rate': 23.0,
            'date_from': '2022-05-01',
            'vehicle_id': cls.batmobile.id,
        })

        bill_1 = cls.env['account.move'].create({
            'partner_id': cls.partner_a.id,
            'move_type': 'in_invoice',
            'date': fields.Date.from_string('2022-01-15'),
            'invoice_date': fields.Date.from_string('2022-01-15'),
            'invoice_line_ids': [
                Command.create({
                    'name': 'Test',
                    'quantity': 1,
                    'price_unit': 100.0,
                    'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    'account_id': cls.company_data['default_account_expense'].id,
                }),
                Command.create({
                    'vehicle_id': cls.batmobile.id,
                    'quantity': 1,
                    'price_unit': 200.0,
                    'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    'account_id': cls.company_data['default_account_expense'].id,
                }),
                Command.create({
                    'vehicle_id': cls.batpod.id,
                    'quantity': 1,
                    'price_unit': 300.0,
                    'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    'account_id': cls.company_data['default_account_expense'].id,
                }),
            ],
        })

        # Create a second bill at a later date in order to have multiple rates in the annual report.
        bill_2 = cls.env['account.move'].create({
            'partner_id': cls.partner_a.id,
            'move_type': 'in_invoice',
            'date': fields.Date.from_string('2022-05-15'),
            'invoice_date': fields.Date.from_string('2022-05-15'),
            'invoice_line_ids': [
                Command.create({
                    'name': 'Test',
                    'quantity': 1,
                    'price_unit': 400.0,
                    'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    'account_id': cls.company_data['default_account_expense'].id,
                }),
                Command.create({
                    'vehicle_id': cls.batmobile.id,
                    'quantity': 1,
                    'price_unit': 500.0,
                    'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    'account_id': cls.company_data['default_account_expense_2'].id,
                }),
                Command.create({
                    'vehicle_id': cls.batmobile.id,
                    'quantity': 1,
                    'price_unit': 600.0,
                    'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    'account_id': cls.company_data['default_account_expense'].id,
                }),
            ],
        })

        # Create a third bill with yet another date.
        bill_3 = cls.env['account.move'].create({
            'partner_id': cls.partner_a.id,
            'move_type': 'in_invoice',
            'date': fields.Date.from_string('2022-08-15'),
            'invoice_date': fields.Date.from_string('2022-08-15'),
            'invoice_line_ids': [
                Command.create({
                    'name': 'Test',
                    'quantity': 1,
                    'price_unit': 700.0,
                    'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    'account_id': cls.company_data['default_account_expense'].id,
                }),
            ],
        })

        (bill_1 + bill_2 + bill_3).action_post()

    def _setup_base_report(self, unfold=False, split=False):
        report = self.env.ref('account_disallowed_expenses.disallowed_expenses_report')
        default_options = {'unfold_all': unfold, 'vehicle_split': split}
        options = self._generate_options(report, '2022-01-01', '2022-12-31', default_options)
        self.env.company.totals_below_sections = False
        return report, options

    def _prepare_column_values(self, lines):
        """ Helper that adds each line's level to its columns, so that the level can be tested in assertLinesValues().
            It also cleans unwanted characters in the line name.
        """
        for line in lines:
            # This is just to prevent the name override in l10n_be_hr_payroll_fleet from making the test crash.
            line['name'] = line['name'].split(' \u2022 ')[0]
            line['columns'].append({'name': line['level']})

    def test_disallowed_expenses_report_unfold_all(self):
        report, options = self._setup_base_report(unfold=True)
        lines = report._get_lines(options)
        self._prepare_column_values(lines)

        self.assertLinesValues(
            # pylint: disable=C0326
            lines,
            #   Name                                          Total Amount     Rate          Disallowed Amount    Level
            [   0,                                            1,               2,            3,                   4],
            [
                ('1234 DNA category',                         2800.0,          '',           864.0,               1),
                  ('600000 Expenses',                         2300.0,          '',           749.0,               2),
                    ('600000 Expenses',                        700.0,          '23.0%',      161.0,               3),
                    ('600000 Expenses',                        600.0,          '23.0%',      138.0,               3),
                    ('600000 Expenses',                        400.0,          '40.0%',      160.0,               3),
                    ('600000 Expenses',                        200.0,          '31.0%',       62.0,               3),
                    ('600000 Expenses',                        300.0,          '56.0%',      168.0,               3),
                    ('600000 Expenses',                        100.0,          '60.0%',       60.0,               3),
                  ('600020 Expenses (copy)',                   500.0,          '23.0%',      115.0,               2),
                    ('600020 Expenses (copy)',                 500.0,          '23.0%',      115.0,               3),
            ],
        )

    def test_disallowed_expenses_report_unfold_all_with_vehicle_split(self):
        report, options = self._setup_base_report(unfold=True, split=True)
        lines = report._get_lines(options)
        self._prepare_column_values(lines)

        self.assertLinesValues(
            # pylint: disable=C0326
            lines,
            #   Name                                          Total Amount     Rate          Disallowed Amount    Level
            [   0,                                            1,               2,            3,                   4],
            [
                ('1234 DNA category',                         2800.0,          '',           864.0,               1),
                  ('Wayne Enterprises/Batmobile/No Plate',    1300.0,          '',           315.0,               2),
                    ('600000 Expenses',                        800.0,          '',           200.0,               3),
                      ('600000 Expenses',                      600.0,          '23.0%',      138.0,               4),
                      ('600000 Expenses',                      200.0,          '31.0%',       62.0,               4),
                    ('600020 Expenses (copy)',                 500.0,          '23.0%',      115.0,               3),
                  ('Wayne Enterprises/Batpod/No Plate',        300.0,          '56.0%',      168.0,               2),
                    ('600000 Expenses',                        300.0,          '56.0%',      168.0,               3),
                  ('600000 Expenses',                         1200.0,          '',           381.0,               2),
                    ('600000 Expenses',                        700.0,          '23.0%',      161.0,               3),
                    ('600000 Expenses',                        400.0,          '40.0%',      160.0,               3),
                    ('600000 Expenses',                        100.0,          '60.0%',       60.0,               3),
            ],
        )
