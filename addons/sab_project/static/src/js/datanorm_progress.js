/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SabDatanormProgress extends Component {
    static template = "sab_project.DatanormProgress";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.wizardId = this.props.action.params.wizard_id;
        this.state = useState({
            progress: 0,
            processed: 0,
            total: 0,
            status: "Import wird vorbereitet …",
            errors: 0,
            lastError: "",
            done: false,
            failed: false,
            busy: true,
        });
        onMounted(() => this._processNextChunk());
    }

    async _processNextChunk() {
        if (this.state.done || this.state.failed) {
            return;
        }
        try {
            const result = await this.orm.call(
                "sab.datanorm.import",
                "action_process_chunk",
                [[this.wizardId]],
                { batch_size: 250 }
            );
            this.state.progress = result.progress || 0;
            this.state.processed = result.processed || 0;
            this.state.total = result.total || 0;
            this.state.status = result.status || "";
            this.state.errors = result.errors || 0;
            this.state.lastError = result.last_error || "";
            this.state.done = Boolean(result.done);
            this.state.failed = Boolean(result.failed);
            this.state.busy = !this.state.done && !this.state.failed;
            if (!this.state.done && !this.state.failed) {
                window.setTimeout(() => this._processNextChunk(), 25);
            }
        } catch (error) {
            this.state.failed = true;
            this.state.busy = false;
            this.state.status = "Import abgebrochen";
            this.state.lastError = error?.message || String(error);
        }
    }

    async openProtocol() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sab.datanorm.import",
            res_id: this.wizardId,
            views: [[false, "form"]],
            target: "new",
        });
    }
}

registry.category("actions").add("sab_datanorm_progress", SabDatanormProgress);
