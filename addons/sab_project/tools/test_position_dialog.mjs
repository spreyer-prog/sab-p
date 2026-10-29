/** Isolated tests of the real frontend callbacks with mocked Odoo services. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const utilsSource = readFileSync(resolve(root, 'static/src/js/position_dialog_utils.js'), 'utf8');
const utilsUrl = 'data:text/javascript;base64,' + Buffer.from(utilsSource).toString('base64');
const { relationId, orderRecord, inComponent, canChoose, choiceValues } = await import(utilsUrl);
let count = 0;
function check(fn) { fn(); count++; }
async function test(fn) { await fn(); count++; }
const order = { resModel: 'sale.order', resId: 10, data: {
    state: 'draft', sab_offer_release_state: 'draft', sab_calculation_source: 'lv',
    sab_project_id: { id: 8 }, company_id: { id: 1 }, partner_id: { id: 2 },
    sab_calculation_line_ids: { records: [] },
} };
function row(values = {}) {
    const result = { resModel: 'sab.offer.calculation.line', model: { root: order },
        data: { line_type: 'item', calculation_item_id: { id: 7 }, quantity: 3,
                description: 'Own text', lv_position: false, ...values },
        async update(values) { Object.assign(this.data, values); },
    };
    return result;
}
check(() => assert.equal(relationId({ id: 7 }), 7));
check(() => assert.equal(relationId([7, 'Name']), 7));
check(() => assert.equal(relationId(false), false));
check(() => assert.equal(relationId('virtual_7'), false));
check(() => assert.equal(orderRecord(row()), order));
check(() => assert.equal(canChoose(row(), order), true));
check(() => assert.equal(canChoose(row({ sab_project_price_bound: true }), order), false));
check(() => assert.equal(canChoose(row({ parent_section_id: { id: 5 } }), order), false));
check(() => assert.equal(canChoose(row({ line_type: 'section' }), order), false));
check(() => assert.equal(canChoose(row(), { ...order, data: { ...order.data, sab_offer_release_state: 'released' } }), false));
check(() => assert.equal(canChoose(row(), { ...order, data: { ...order.data, sab_calculation_source: 'schematic' } }), true));
check(() => {
    const r = row(); order.data.sab_calculation_line_ids.records = [{ data: { line_type: 'section' } }, r];
    assert.equal(inComponent(r, order), true);
    assert.equal(canChoose(r, order), false);
});
check(() => {
    const r = row(); order.data.sab_calculation_line_ids.records = [{ data: { line_type: 'section' } }, { data: { line_type: 'section_end' } }, r];
    assert.equal(inComponent(r, order), false);
});
check(() => assert.deepEqual(choiceValues('existing', ' 1.1.4 ', false),
    { sab_position_choice: 'existing', lv_position: '1.1.4', is_ntg: false }));
check(() => assert.deepEqual(choiceValues('existing', 'NTG 7', true),
    { sab_position_choice: 'existing', lv_position: 'NTG 7', is_ntg: true }));
check(() => assert.deepEqual(choiceValues('new_ntg'),
    { sab_position_choice: 'new_ntg', lv_position: false, is_ntg: false }));
check(() => assert.throws(() => choiceValues('new_lv', 'NTG 8')));
check(() => assert.throws(() => choiceValues('new_lv', '  ')));

// Import the production dialog module with only framework/service dependencies mocked.
let source = readFileSync(resolve(root, 'static/src/js/offer_position_dialog.js'), 'utf8');
source = source.replace(/^import .*;\n/gm, '');
const stubs = `
import { relationId, orderRecord, canChoose, articleKey, choiceValues } from ${JSON.stringify(utilsUrl)};
class Component {}
class Many2OneField extends Component { get m2oProps() { return { update: (value) => this.props.record.update({ [this.props.name]: value }) }; } }
const Dialog = class {};
const registry = { category: () => ({ add() {} }) };
const buildM2OFieldDescription = (component) => ({ component });
const standardFieldProps = {};
const onWillUnmount = () => {};
const useService = () => {};
const useState = (values) => values;
`;
const ui = await import('data:text/javascript;base64,' + Buffer.from(stubs + source).toString('base64'));
function component(r, payload) {
    order.data.sab_calculation_line_ids.records = [r];
    return { props: { record: r }, _positionRequest: 0, _positionDestroyed: false,
        orm: { async call(model, method, args) {
            assert.equal(model, 'sab.offer.calculation.line');
            assert.equal(method, 'sab_position_dialog_options');
            assert.equal(args[0].calculation_item_id, 7);
            return payload;
        } },
        dialog: { add(type, props) { this.opened = { type, props }; } },
    };
}
const payload = { positions: [{ code: '1.1.1', is_ntg: false }, { code: '1.1.4', is_ntg: false }], can_new_lv: true, can_new_ntg: true };
await test(async () => {
    const r = row(); const c = component(r, payload);
    await ui.openPositionDialog(c, true);
    assert.equal(c.dialog.opened.type, ui.SabPositionDialog);
    await c.dialog.opened.props.select(choiceValues('existing', '1.1.4'));
    assert.equal(r.data.lv_position, '1.1.4');
    assert.equal(r.data.quantity, 3); assert.equal(r.data.description, 'Own text');
    assert.equal(order.data.sab_calculation_line_ids.records.length, 1);
});
await test(async () => {
    const r = row(); const c = component(r, payload);
    await ui.openPositionDialog(c, true);
    await c.dialog.opened.props.select(choiceValues('new_ntg'));
    assert.equal(r.data.sab_position_choice, 'new_ntg'); assert.equal(r.data.lv_position, false);
});
await test(async () => {
    const r = row(); const c = component(r, { ...payload, positions: [payload.positions[0]] });
    await ui.openPositionDialog(c, true);
    assert.ok(c.dialog.opened, 'A single previous position must also allow NEW vs existing.');
});
await test(async () => {
    const r = row({ sab_position_choice: 'pending' }); const c = component(r, { ...payload, positions: [] });
    await ui.openPositionDialog(c, true);
    assert.equal(c.dialog.opened, undefined); assert.equal(r.data.sab_position_choice, 'auto');
});
await test(async () => {
    const r = row(); const c = component(r, payload);
    await ui.openPositionDialog(c);
    r.data.calculation_item_id = { id: 8 };
    await assert.rejects(() => c.dialog.opened.props.select(choiceValues('existing', '1.1.1')));
});
await test(async () => {
    const r = row(); const c = component(r, payload);
    c.orm.call = async () => { r.data.calculation_item_id = { id: 8 }; return payload; };
    await ui.openPositionDialog(c); assert.equal(c.dialog.opened, undefined);
});
await test(async () => {
    const r = row(); const c = component(r, payload);
    await ui.openPositionDialog(c); order.data.sab_calculation_line_ids.records = [];
    await assert.rejects(() => c.dialog.opened.props.select(choiceValues('existing', '1.1.1')));
});
await test(async () => {
    const r = row({ parent_section_id: { id: 7 } }); const c = component(r, payload);
    c.orm.call = async () => { throw new Error('Bauteil must not request direct LV options'); };
    await ui.openPositionDialog(c); assert.equal(c.dialog.opened, undefined);
});
await test(async () => {
    const r = row({ sab_position_choice: 'pending' }); const c = component(r, payload);
    const before = { ...r.data };
    await ui.openPositionDialog(c);
    // Closing without selecting executes no callback and changes no data.
    assert.deepEqual(r.data, before);
});
await test(async () => {
    const r = row(); const c = component(r, payload);
    c._positionDestroyed = true;
    await ui.openPositionDialog(c); assert.equal(c.dialog.opened, undefined);
});
await test(async () => {
    const r = row({ calculation_item_id: false });
    const c = component(r, payload);
    const field = new ui.SabPositionArticleField();
    Object.assign(field, c); field.props = { record: r, name: 'calculation_item_id' };
    await field.m2oProps.update({ id: 7, display_name: 'Selected' });
    assert.equal(r.data.sab_position_choice, 'pending');
    assert.ok(c.dialog.opened);
});
await test(async () => {
    const r = row({ calculation_item_id: false, lv_position: '4.3.2' });
    const c = component(r, payload);
    const field = new ui.SabPositionArticleField();
    Object.assign(field, c); field.props = { record: r, name: 'calculation_item_id' };
    await field.m2oProps.update({ id: 7, display_name: 'Selected' });
    assert.equal(r.data.lv_position, '4.3.2'); assert.equal(c.dialog.opened, undefined);
});
await test(async () => {
    const r = row({ calculation_item_id: false });
    const c = component(r, payload);
    order.data.sab_calculation_line_ids.records = [{ data: { line_type: 'section' } }, r];
    const field = new ui.SabPositionArticleField();
    Object.assign(field, c); field.props = { record: r, name: 'calculation_item_id' };
    await field.m2oProps.update({ id: 7, display_name: 'Selected' });
    assert.equal(c.dialog.opened, undefined); assert.notEqual(r.data.sab_position_choice, 'pending');
});
await test(async () => {
    const r = row({ calculation_item_id: false }); const c = component(r, payload);
    c.orm.call = async () => { throw new Error('Simulated network failure'); };
    c.notification = { add() {} };
    const field = new ui.SabPositionArticleField();
    Object.assign(field, c); field.props = { record: r, name: 'calculation_item_id' };
    await field.m2oProps.update({ id: 7, display_name: 'Selected' });
    assert.equal(r.data.sab_position_choice, 'pending'); assert.equal(r.data.lv_position, false);
});
console.log(`${count} isolated frontend checks passed (framework/services mocked; no live Odoo browser).`);
