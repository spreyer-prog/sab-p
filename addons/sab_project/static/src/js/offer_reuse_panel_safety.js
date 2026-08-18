/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SabOfferReusePanel } from "./offer_reuse_panel";

patch(SabOfferReusePanel.prototype, {
    get canEdit() {
        return ["draft", "sent"].includes(this.props.record.data.state) && !this.state.busy;
    },

    async ensureSavedOrder() {
        // Reuse actions operate server-side. Always flush the current form first,
        // otherwise a freshly entered Bauteil or changed quantity could be lost
        // when the record is reloaded after the RPC call.
        await this.props.record.save();
        if (!this.props.record.resId) {
            throw new Error("Das Angebot konnte nicht gespeichert werden.");
        }
        return this.props.record.resId;
    },

    async refresh() {
        if (this.props.record.data.sab_project_id) {
            await this.props.record.save();
        }
        await this.loadPayload();
    },
});
