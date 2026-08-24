/** @odoo-module **/

import { Component, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SabSuiteActionRouter extends Component {
    static template = "sab_project.SuiteActionRouter";

    setup() {
        this.actionService = useService("action");
        this.menuService = useService("menu");
        onMounted(() => this._openAction());
    }

    async _openAction() {
        const params = this.props.action.params || {};
        if (params.menu_id) {
            this.menuService.setCurrentMenu(params.menu_id);
        }
        await this.actionService.doAction(params.action, {
            clearBreadcrumbs: true,
            onActionReady: () => {
                if (params.menu_id) {
                    this.menuService.setCurrentMenu(params.menu_id);
                }
            },
        });
    }
}

registry.category("actions").add("sab_open_suite_action", SabSuiteActionRouter);
