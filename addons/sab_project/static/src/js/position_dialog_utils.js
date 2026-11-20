/** @odoo-module **/
// Pure helpers shared by the picker and its isolated regression tests.
export function relationId(value) {
    const id = Array.isArray(value) ? value[0] : (value?.id ?? value);
    return Number.isInteger(id) && id > 0 ? id : false;
}
export function orderRecord(row) {
    let parent = row;
    while (parent && parent.resModel !== "sale.order") {
        parent = parent._parentRecord;
    }
    return parent || (row.model.root?.resModel === "sale.order" ? row.model.root : null);
}
export function inComponent(row, order) {
    if (relationId(row.data.parent_section_id)) {
        return true;
    }
    // Unsaved rows may not have their parent_section_id normalised yet.
    let section = false;
    for (const candidate of order.data.sab_calculation_line_ids?.records || []) {
        if (candidate === row) {
            return section;
        }
        const kind = candidate.data.line_type;
        if (kind === "section") section = true;
        else if (["section_end", "cabinet", "cabinet_end"].includes(kind)) section = false;
    }
    return false;
}
export function canChoose(row, order) {
    return !!order && ["lv", "schematic"].includes(order.data.sab_calculation_source)
        && !["sale", "done", "cancel"].includes(order.data.state)
        && order.data.sab_offer_release_state !== "released"
        && (!row.data.line_type || row.data.line_type === "item")
        && !row.data.sab_project_price_bound && (!relationId(row.resId) || !row.data.lv_position_locked)
        && !inComponent(row, order);
}
export function articleKey(row) {
    return JSON.stringify([relationId(row.data.calculation_item_id), relationId(row.data.odoo_product_id)]);
}
export function choiceValues(mode, code = "", isNtg = false) {
    if (mode === "new_ntg") {
        return { sab_position_choice: mode, lv_position: false, is_ntg: false };
    }
    code = String(code || "").trim();
    if (!code) throw new Error("Bitte eine LV-Position auswählen oder eingeben.");
    if (mode === "new_lv" && /^NTG/i.test(code)) {
        throw new Error("Für einen Nachtrag bitte ‚Neue NTG‘ wählen.");
    }
    if (!["new_lv", "existing"].includes(mode)) throw new Error("Ungültige Auswahl.");
    return { sab_position_choice: mode, lv_position: code, is_ntg: !!isNtg };
}
