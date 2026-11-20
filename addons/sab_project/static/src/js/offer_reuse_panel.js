/** @odoo-module **/

import {
    Component,
    onMounted,
    onPatched,
    onWillUnmount,
    onWillUpdateProps,
    useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const REUSE_MIME = "application/x-sab-offer-reuse";

export class SabOfferReusePanel extends Component {
    static template = "sab_project.OfferReusePanel";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: false,
            busy: false,
            activeTab: "lv",
            search: "",
            payload: {
                editable: false,
                project: false,
                lv_positions: [],
                project_components: [],
                library_components: [],
            },
        });
        this.dropTarget = null;
        this.dragPayload = null;
        this._boundDragOver = (event) => this.onExternalDragOver(event);
        this._boundDragLeave = (event) => this.onExternalDragLeave(event);
        this._boundDrop = (event) => this.onExternalDrop(event);

        onMounted(async () => {
            this.toggleFormMode(this.hasProject);
            this.bindCalculationDropTarget();
            await this.loadPayload();
        });
        onPatched(() => {
            this.toggleFormMode(this.hasProject);
            this.bindCalculationDropTarget();
        });
        onWillUpdateProps(async (nextProps) => {
            const currentKey = this.recordKey(this.props.record);
            const nextKey = this.recordKey(nextProps.record);
            if (currentKey !== nextKey) {
                this.toggleFormMode(Boolean(nextProps.record.data.sab_project_id));
                await this.loadPayload(nextProps.record);
            }
        });
        onWillUnmount(() => {
            this.unbindCalculationDropTarget();
            this.toggleFormMode(false);
            this.dragPayload = null;
        });
    }

    recordKey(record) {
        return [
            record.resId || 0,
            Boolean(record.data.sab_project_id),
            record.data.state || "",
            record.data.sab_offer_release_state || "",
            record.data.sab_calculation_source || "",
        ].join("|");
    }

    get hasProject() {
        return Boolean(this.props.record.data.sab_project_id);
    }

    get canEdit() {
        return (
            ["draft", "sent"].includes(this.props.record.data.state) &&
            this.props.record.data.sab_offer_release_state !== "released" &&
            !this.state.busy
        );
    }

    get searchTerm() {
        return (this.state.search || "").trim().toLocaleLowerCase();
    }

    includesSearch(...values) {
        if (!this.searchTerm) {
            return true;
        }
        return values
            .filter((value) => value !== undefined && value !== null)
            .some((value) => String(value).toLocaleLowerCase().includes(this.searchTerm));
    }

    get filteredLvPositions() {
        return this.state.payload.lv_positions.filter((item) =>
            this.includesSearch(item.position, item.source_name, item.first_offer)
        );
    }

    get filteredCurrentComponents() {
        return this.state.payload.project_components.filter(
            (item) =>
                item.is_current &&
                this.includesSearch(
                    item.name,
                    item.positions,
                    item.offers_text,
                    item.offer
                )
        );
    }

    get filteredPreviousComponents() {
        return this.state.payload.project_components.filter(
            (item) =>
                !item.is_current &&
                this.includesSearch(
                    item.name,
                    item.positions,
                    item.offers_text,
                    item.offer
                )
        );
    }

    get filteredLibraryComponents() {
        return this.state.payload.library_components.filter((item) =>
            this.includesSearch(item.name, item.source_project, item.source_offer)
        );
    }

    setTab(tab) {
        this.state.activeTab = tab;
    }

    onSearchInput(event) {
        this.state.search = event.target.value;
    }

    toggleFormMode(enabled) {
        const form = this.el?.closest(".o_form_view");
        if (form) {
            form.classList.toggle("o_sab_reuse_active", Boolean(enabled));
        }
    }

    bindCalculationDropTarget() {
        if (!this.el) {
            return;
        }
        const form = this.el.closest(".o_form_view");
        const target = form?.querySelector(
            ".o_field_widget[name='sab_calculation_line_ids'], [name='sab_calculation_line_ids'].o_field_widget"
        );
        if (target === this.dropTarget) {
            return;
        }
        this.unbindCalculationDropTarget();
        if (!target) {
            return;
        }
        this.dropTarget = target;
        target.classList.add("o_sab_reuse_drop_target");
        target.addEventListener("dragover", this._boundDragOver);
        target.addEventListener("dragleave", this._boundDragLeave);
        target.addEventListener("drop", this._boundDrop);
    }

    unbindCalculationDropTarget() {
        if (!this.dropTarget) {
            return;
        }
        this.dropTarget.classList.remove(
            "o_sab_reuse_drop_target",
            "o_sab_reuse_drop_ready"
        );
        this.dropTarget.removeEventListener("dragover", this._boundDragOver);
        this.dropTarget.removeEventListener("dragleave", this._boundDragLeave);
        this.dropTarget.removeEventListener("drop", this._boundDrop);
        this.dropTarget = null;
    }

    async loadPayload(record = this.props.record) {
        const hasProject = Boolean(record.data.sab_project_id);
        const orderId = record.resId;
        if (!hasProject || !orderId) {
            this.state.payload = {
                editable: false,
                project: false,
                lv_positions: [],
                project_components: [],
                library_components: [],
            };
            return;
        }
        this.state.loading = true;
        try {
            this.state.payload = await this.orm.call(
                "sale.order",
                "sab_offer_reuse_payload",
                [[orderId]]
            );
        } catch (error) {
            this.notifyError(error);
        } finally {
            this.state.loading = false;
        }
    }

    async ensureSavedOrder() {
        await this.props.record.save();
        if (!this.props.record.resId) {
            throw new Error("Das Angebot konnte nicht gespeichert werden.");
        }
        return this.props.record.resId;
    }

    hasReuseDragType(event) {
        const types = Array.from(event.dataTransfer?.types || []);
        return Boolean(this.dragPayload || types.includes(REUSE_MIME));
    }

    onDragStart(event) {
        const kind = event.currentTarget.dataset.kind;
        const id = Number(event.currentTarget.dataset.id);
        if (!kind || !id || !this.canEdit) {
            event.preventDefault();
            return;
        }
        this.dragPayload = { kind, id };
        event.dataTransfer.effectAllowed = "copy";
        event.dataTransfer.setData(REUSE_MIME, JSON.stringify(this.dragPayload));
        event.dataTransfer.setData("text/plain", `${kind}:${id}`);
    }

    onDragEnd() {
        this.dragPayload = null;
        this.dropTarget?.classList.remove("o_sab_reuse_drop_ready");
    }

    readDropData(event) {
        const raw = event.dataTransfer?.getData(REUSE_MIME);
        if (raw) {
            try {
                const data = JSON.parse(raw);
                if (data?.kind && Number(data.id)) {
                    return { kind: data.kind, id: Number(data.id) };
                }
            } catch {
                // Fall through to the same-page drag payload.
            }
        }
        return this.dragPayload;
    }

    onExternalDragOver(event) {
        if (!this.canEdit || !this.hasReuseDragType(event)) {
            return;
        }
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
        this.dropTarget?.classList.add("o_sab_reuse_drop_ready");
    }

    onExternalDragLeave(event) {
        if (!event.currentTarget.contains(event.relatedTarget)) {
            this.dropTarget?.classList.remove("o_sab_reuse_drop_ready");
        }
    }

    async onExternalDrop(event) {
        const data = this.readDropData(event);
        this.dropTarget?.classList.remove("o_sab_reuse_drop_ready");
        this.dragPayload = null;
        if (!data || !this.canEdit) {
            return;
        }
        event.preventDefault();
        await this.addEntry(data.kind, data.id);
    }

    onPanelDragOver(event) {
        if (!this.canEdit || !this.hasReuseDragType(event)) {
            return;
        }
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
        event.currentTarget.classList.add("o_sab_reuse_drop_ready");
    }

    onPanelDragLeave(event) {
        event.currentTarget.classList.remove("o_sab_reuse_drop_ready");
    }

    async onPanelDrop(event) {
        const data = this.readDropData(event);
        event.currentTarget.classList.remove("o_sab_reuse_drop_ready");
        this.dragPayload = null;
        if (!data || !this.canEdit) {
            return;
        }
        event.preventDefault();
        await this.addEntry(data.kind, data.id);
    }

    async addEntry(kind, id) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const orderId = await this.ensureSavedOrder();
            const result = await this.orm.call(
                "sale.order",
                "sab_offer_add_reuse_entry",
                [[orderId], kind, Number(id)]
            );
            await this.props.record.load();
            await this.loadPayload();
            this.notification.add(result.message || "Position wurde übernommen.", {
                type: "success",
            });
        } catch (error) {
            this.notifyError(error);
        } finally {
            this.state.busy = false;
        }
    }

    async saveComponent(sectionId) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const orderId = await this.ensureSavedOrder();
            const result = await this.orm.call(
                "sale.order",
                "sab_offer_save_component_template",
                [[orderId], Number(sectionId)]
            );
            await this.loadPayload();
            this.notification.add(result.message, { type: "success" });
        } catch (error) {
            this.notifyError(error);
        } finally {
            this.state.busy = false;
        }
    }

    async refresh() {
        if (this.props.record.data.sab_project_id) {
            await this.props.record.save();
        }
        await this.loadPayload();
    }

    formatAmount(value) {
        return new Intl.NumberFormat("de-DE", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(Number(value || 0));
    }

    notifyError(error) {
        const message =
            error?.data?.message ||
            error?.cause?.data?.message ||
            error?.message ||
            String(error);
        this.notification.add(message, { type: "danger", sticky: true });
    }
}

registry.category("view_widgets").add("sab_offer_reuse_panel", {
    component: SabOfferReusePanel,
    fieldDependencies: [
        { name: "sab_project_id", type: "many2one" },
        { name: "sab_offer_reference", type: "char" },
        { name: "sab_offer_release_state", type: "selection" },
        { name: "sab_calculation_source", type: "selection" },
        { name: "state", type: "selection" },
    ],
});
