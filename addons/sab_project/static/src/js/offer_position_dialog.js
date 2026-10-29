/** @odoo-module **/
import { Component, onWillUnmount, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Many2OneField, buildM2OFieldDescription } from "@web/views/fields/many2one/many2one_field";
import { relationId, orderRecord, canChoose, articleKey, choiceValues } from "@sab_project/js/position_dialog_utils";

export class SabPositionDialog extends Component {
    static template = "sab_project.PositionDialog";
    static components = { Dialog };
    static props = { close: Function, payload: Object, select: Function };
    setup() {
        this.state = useState({ newCode: "", busy: false, error: "" });
    }
    formatPrice(entry) {
        return entry.price === null || entry.price === undefined ? "—"
            : new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(entry.price)
                + " " + (entry.currency || "");
    }
    async choose(mode, code = "", isNtg = false) {
        if (this.state.busy) return;
        this.state.busy = true;
        this.state.error = "";
        try {
            await this.props.select(choiceValues(mode, code, isNtg));
            this.props.close();
        } catch (error) {
            this.state.error = error.message || "Die Auswahl konnte nicht übernommen werden.";
        } finally {
            this.state.busy = false;
        }
    }
}

function setupPicker(component) {
    component.orm = useService("orm");
    component.dialog = useService("dialog");
    component.notification = useService("notification");
    component._positionRequest = 0;
    component._positionDestroyed = false;
    onWillUnmount(() => {
        component._positionDestroyed = true;
        component._positionRequest++;
    });
}

export async function openPositionDialog(component, automatic = false) {
    const row = component.props.record;
    const order = orderRecord(row);
    if (!canChoose(row, order)) return;
    const key = articleKey(row);
    const generation = ++component._positionRequest;
    const payload = await component.orm.call("sab.offer.calculation.line", "sab_position_dialog_options", [{
        order_id: relationId(order.resId), line_id: relationId(row.resId),
        project_id: relationId(order.data.sab_project_id), company_id: relationId(order.data.company_id),
        partner_id: relationId(order.data.partner_id),
        calculation_item_id: relationId(row.data.calculation_item_id),
        odoo_product_id: relationId(row.data.odoo_product_id),
    }]);
    if (component._positionDestroyed || generation !== component._positionRequest || key !== articleKey(row)) return;
    if (automatic && !payload.positions.length) {
        // No previous identity exists: keep the established first-LV / new-NTG
        // save behaviour. Do not allocate a number during autocomplete.
        await row.update({ sab_position_choice: "auto" });
        return;
    }
    component.dialog.add(SabPositionDialog, {
        payload,
        select: async (values) => {
            if (key !== articleKey(row) || !canChoose(row, order)) {
                throw new Error("Die Zeile wurde inzwischen geändert. Bitte die Auswahl erneut öffnen.");
            }
            const rows = order.data.sab_calculation_line_ids?.records;
            if (rows && !rows.includes(row)) throw new Error("Die Angebotszeile existiert nicht mehr.");
            // Update only this existing form row. No save(), release(), create()
            // or second quotation line is triggered by this selection.
            await row.update(values);
        },
    });
}

export class SabPositionArticleField extends Many2OneField {
    setup() {
        setupPicker(this);
    }
    get m2oProps() {
        const props = super.m2oProps;
        return { ...props, update: async (value, options = {}) => {
            const row = this.props.record;
            const before = relationId(row.data[this.props.name]);
            const after = relationId(value);
            const order = orderRecord(row);
            const explicitCode = !!String(row.data.lv_position || "").trim();
            const choose = after && before !== after && !explicitCode && canChoose(row, order);
            if (!choose) return props.update(value, options);
            await row.update({ [this.props.name]: value, sab_position_choice: "pending",
                               lv_position: false, is_ntg: false }, options);
            try {
                await openPositionDialog(this, true);
            } catch (error) {
                this.notification.add("LV-Auswahl konnte nicht geladen werden. Bitte ‚LV / NTG wählen‘ anklicken.",
                                      { type: "danger" });
                // Keep the unresolved row, quantity, text and price preview.
                // A read failure must never silently allocate a different code.
            }
        } };
    }
}
registry.category("fields").add("sab_position_article", buildM2OFieldDescription(SabPositionArticleField));

export class SabPositionPickerField extends Component {
    static template = "sab_project.PositionPickerField";
    static props = { ...standardFieldProps };
    setup() {
        setupPicker(this);
    }
    get enabled() {
        const row = this.props.record;
        return !this.props.readonly && canChoose(row, orderRecord(row))
            && !!(relationId(row.data.calculation_item_id) || relationId(row.data.odoo_product_id));
    }
    get label() {
        return this.props.record.data[this.props.name] === "new_ntg" ? "Neue NTG" : "LV / NTG wählen";
    }
    get title() {
        return this.props.record.data[this.props.name] === "new_ntg"
            ? "Neue NTG – Nummer wird beim Speichern vergeben." : "Vorhandene LV-/NTG-Position übernehmen oder neue Position anlegen.";
    }
    async open() {
        if (!this.enabled) return;
        try {
            await openPositionDialog(this);
        } catch (error) {
            this.notification.add(error.message || "LV-Auswahl konnte nicht geladen werden.", { type: "danger" });
        }
    }
}
registry.category("fields").add("sab_position_picker", {
    component: SabPositionPickerField, supportedTypes: ["selection"],
});
