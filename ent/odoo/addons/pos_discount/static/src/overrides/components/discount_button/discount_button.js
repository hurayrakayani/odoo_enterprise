/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { parseFloat } from "@web/views/fields/parsers";

export class DiscountButton extends Component {
    static template = "pos_discount.DiscountButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
    }

    async click() {
        // First popup: select discount type (percentage or fixed)
        const { confirmed: typeConfirmed, payload: discountType } = await this.popup.add(SelectionPopup, {
            title: _t("Discount Type"),
            list: [
                { id: 1, label: _t("Percentage"), item: "percentage", isSelected: true },
                { id: 2, label: _t("Fixed Amount"), item: "fixed" },
            ],
            isInputSelected: true,
        });
        if (!typeConfirmed) return;

        // Second popup: enter the discount value
        const { confirmed, payload } = await this.popup.add(NumberPopup, {
            title: discountType === "percentage" ? _t("Discount Percentage") : _t("Discount Amount"),
            startingValue: this.pos.config.discount_pc || 0,
            isInputSelected: true,
        });
        if (confirmed) {
            await this.apply_discount(parseFloat(payload), discountType);
        }
    }

    async apply_discount(value, discountType) {
        const order = this.pos.get_order();
        if (!order) return;

        const product = this.pos.db.get_product_by_id(this.pos.config.discount_product_id?.[0]);
        if (!product) {
            await this.popup.add(ErrorPopup, {
                title: _t("No discount product found"),
                body: _t("The discount product seems misconfigured. Ensure it is marked 'Can be Sold' and 'Available in Point of Sale'."),
            });
            return;
        }

        // Only remove existing discount lines for percentage discounts.
        // For fixed amount discounts, we want each discount application to add a new line.
        if (discountType === "percentage") {
            order.get_orderlines()
                .filter(line => line.get_product() === product)
                .forEach(line => order._unlinkOrderline(line));
        }

        const groupedLines = order.get_orderlines_grouped_by_tax_ids();

        // For fixed discount, first compute the total base across all tax groups.
        let totalBaseToDiscount = 0;
        if (discountType === "fixed") {
            for (const [tax_ids, lines] of Object.entries(groupedLines)) {
                const tax_ids_array = tax_ids.split(",").filter(Boolean).map(Number);
                // Calculate the total base amount for each group eligible for discount.
                const baseAmount = order.calculate_base_amount(
                    tax_ids_array,
                    lines.filter(ll => ll.isGlobalDiscountApplicable())
                );
                totalBaseToDiscount += baseAmount;
            }
            // If there is no eligible base amount, no discount can be applied.
            if (totalBaseToDiscount === 0) return;
        }

        // Loop over each tax group and apply the discount proportionally.
        for (const [tax_ids, lines] of Object.entries(groupedLines)) {
            const tax_ids_array = tax_ids.split(",").filter(Boolean).map(Number);
            const baseToDiscount = order.calculate_base_amount(
                tax_ids_array,
                lines.filter(ll => ll.isGlobalDiscountApplicable())
            );

            // Compute discount for the current tax group.
            let discount;
            if (discountType === "percentage") {
                discount = (-value / 100.0) * baseToDiscount;
            } else {
                // For fixed discount, apply discount proportionally.
                discount = -value * (baseToDiscount / totalBaseToDiscount);
            }

            // If discount is not negative (for some reason), skip this group.
            if (discount >= 0) continue;

            order.add_product(product, {
                price: discount,
                lst_price: discount,
                tax_ids: tax_ids_array,
                merge: false,
                description: `${discountType === "percentage" ? value + "%" : this.pos.currency.symbol + value}, ` +
                    (tax_ids_array.length
                        ? _t("Tax: %s", tax_ids_array.map(taxId => this.pos.taxes_by_id[taxId].amount + "%").join(", "))
                        : _t("No tax")),
                extras: { price_type: "automatic" },
            });
        }
    }
}

ProductScreen.addControlButton({
    component: DiscountButton,
    condition() {
        const { module_pos_discount, discount_product_id } = this.pos.config;
        return module_pos_discount && discount_product_id;
    },
});
