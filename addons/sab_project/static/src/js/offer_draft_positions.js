/** @odoo-module **/
import { useEffect } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { SabOfferReusePanel } from "@sab_project/js/offer_reuse_panel";

const widget = registry.category("view_widgets").get("sab_offer_reuse_panel");
if (!widget.fieldDependencies.some((field) => field.name === "write_date")) {
    widget.fieldDependencies.push({ name: "write_date", type: "datetime" });
}

patch(SabOfferReusePanel.prototype, {
    setup() {
        super.setup(...arguments);
        this._savedPositionKey = this.savedPositionKey();
        useEffect(() => {
            const key = this.savedPositionKey();
            if (!this.props.record.isDirty && key !== this._savedPositionKey) {
                this._savedPositionKey = key;
                // Read only. Never auto-save or release an unfinished quotation.
                void this.loadPayload();
            }
        }, () => [this.savedPositionKey(), this.props.record.isDirty]);
    },
    savedPositionKey() {
        const record = this.props.record;
        const lines = record.data.sab_calculation_line_ids?.records || [];
        return JSON.stringify([
            record.resId || 0, String(record.data.write_date || ""),
            record.data.sab_offer_release_state,
            lines.map((line) => [line.resId, line.data.lv_position, line.data.is_ntg,
                line.data.calculation_item_id, line.data.odoo_product_id]),
        ]);
    },
});
