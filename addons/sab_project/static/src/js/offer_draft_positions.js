/** @odoo-module **/
import { onWillUnmount, useEffect } from "@odoo/owl";
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
        this._positionLoadSequence = 0;
        this._positionPanelDestroyed = false;
        onWillUnmount(() => {
            this._positionPanelDestroyed = true;
            this._positionLoadSequence++;
        });
        useEffect(() => {
            const record = this.props.record;
            const key = this.savedPositionKey();
            // Odoo 19: dirty is the reactive boolean; isDirty() is an async
            // method. Treating the method as a boolean blocked every refresh.
            if (!record.dirty && key !== this._savedPositionKey) {
                this._savedPositionKey = key;
                // Read only: never save or release an unfinished quotation.
                void this.loadPayload(record);
            }
        }, () => [this.savedPositionKey(), this.props.record.dirty]);
    },

    savedPositionKey() {
        const record = this.props.record;
        const lineKey = (field) => (record.data[field]?.records || []).map((line) => [
            line.resId || 0, line.data.line_type, line.data.lv_position,
            line.data.is_ntg, line.data.calculation_item_id, line.data.odoo_product_id,
            line.data.quantity, line.data.description,
        ]);
        return JSON.stringify([
            record.resId || 0, record.data.sab_project_id || false,
            String(record.data.write_date || ""), record.data.state,
            record.data.sab_offer_release_state,
            lineKey("sab_calculation_line_ids"),
            lineKey("sab_material_calculation_line_ids"),
        ]);
    },

    async loadPayload(record = this.props.record) {
        const request = ++this._positionLoadSequence;
        const orderId = record.resId;
        const isCurrent = () => !this._positionPanelDestroyed
            && request === this._positionLoadSequence;
        if (!record.data.sab_project_id || !orderId) {
            this.state.loading = false;
            this.state.payload = {
                editable: false, project: false, lv_positions: [],
                project_components: [], library_components: [],
            };
            return;
        }
        this.state.loading = true;
        try {
            const payload = await this.orm.call(
                "sale.order", "sab_offer_reuse_payload", [[orderId]]
            );
            // A slower previous request must not restore the old empty panel.
            if (isCurrent()) {
                this.state.payload = payload;
            }
        } catch (error) {
            if (isCurrent()) {
                this.notifyError(error);
            }
        } finally {
            if (isCurrent()) {
                this.state.loading = false;
            }
        }
    },
});
