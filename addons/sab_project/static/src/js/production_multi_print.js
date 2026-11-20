/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SabProductionMultiPrint extends Component {
    static template = "sab_project.ProductionMultiPrint";

    setup() {
        this.actionService = useService("action");
        this.menuService = useService("menu");
        this.state = useState({
            current: 0,
            total: (this.props.action.params.jobs || []).length,
            label: "Druckaufträge werden vorbereitet …",
            printer: "",
            done: false,
            failed: false,
            error: "",
        });
        onMounted(() => this._run());
    }

    async _run() {
        const jobs = this.props.action.params.jobs || [];
        const menuId = this.props.action.params.menu_id;
        if (menuId) {
            this.menuService.setCurrentMenu(menuId);
        }
        try {
            for (const job of jobs) {
                this.state.current += 1;
                this.state.label = job.label || "Fertigungsdokument";
                this.state.printer = job.printer_name || "PDF-Drucker";
                await this.actionService.doAction(job.action, {
                    clearBreadcrumbs: false,
                });
            }
            this.state.done = true;
            this.state.label = "Alle Druckaufträge wurden einzeln erzeugt.";
        } catch (error) {
            this.state.failed = true;
            this.state.error = error?.message || String(error);
        }
    }
}

registry.category("actions").add("sab_production_multi_print", SabProductionMultiPrint);
