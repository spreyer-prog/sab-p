// Isolated regression tests for the actual frontend patch (no Odoo browser).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const file = fileURLToPath(new URL('../static/src/js/offer_draft_positions.js', import.meta.url));
const code = fs.readFileSync(file, 'utf8').replace(/^import .*;\n/gm, '');

function fixture(record = {
    resId: 100, dirty: false, isDirty: async () => false,
    data: {sab_project_id: [1, 'Test'], write_date: 't0', state: 'draft',
           sab_offer_release_state: 'draft', sab_calculation_line_ids: {records: []}},
}) {
    const effects = [], unmount = [], calls = [];
    const widget = {fieldDependencies: []};
    class Panel {
        setup() {
            this.state = {loading: false, payload: {lv_positions: []}};
            this.orm = {call: async (...args) => {
                calls.push(args);
                return {lv_positions: [{position: '1.1.1', position_status: 'Entwurf'}]};
            }};
            this.notifyError = (error) => {throw error;};
        }
    }
    const sandbox = {
        SabOfferReusePanel: Panel,
        registry: {category: () => ({get: () => widget})},
        onWillUnmount: (callback) => unmount.push(callback),
        useEffect: (callback, dependencies) => effects.push({callback, dependencies, previous: undefined}),
        patch: (prototype, extension) => {
            const previous = Object.create(Object.getPrototypeOf(prototype));
            Object.defineProperties(previous, Object.getOwnPropertyDescriptors(prototype));
            Object.setPrototypeOf(extension, previous);
            Object.defineProperties(prototype, Object.getOwnPropertyDescriptors(extension));
        },
    };
    vm.runInNewContext(code, sandbox, {filename: file});
    const panel = new Panel(); panel.props = {record}; panel.setup();
    async function render() {
        for (const effect of effects) {
            const deps = effect.dependencies();
            if (!effect.previous || deps.some((d,i) => !Object.is(d, effect.previous[i]))) {
                effect.previous = deps;
                effect.callback();
            }
        }
        await Promise.resolve(); await Promise.resolve();
    }
    return {panel, record, calls, render, unmount, widget};
}

function putLine(record, id, lv='1.1.1', field='sab_calculation_line_ids') {
    record.data[field] = {records: [{resId: id, data: {
        line_type: 'item', lv_position: lv, is_ntg: false,
        calculation_item_id: [1, 'Test'], quantity: 1,
    }}]};
}

test('regression: isDirty is a function, not the reactive dirty flag', () => {
    const {record} = fixture();
    assert.equal(!record.isDirty, false);  // exact old bug
    assert.equal(!record.dirty, true);
});

test('successful draft save refreshes LV panel without release or autosave', async () => {
    const f = fixture(); let saves=0;
    f.record.save = () => {saves++;};
    await f.render();
    f.record.dirty=true; putLine(f.record, 0); await f.render();
    assert.equal(f.calls.length, 0);
    f.record.dirty=false; putLine(f.record, 101); f.record.data.write_date='t1';
    await f.render();
    assert.equal(f.calls.length, 1);
    assert.equal(f.panel.state.payload.lv_positions[0].position_status, 'Entwurf');
    assert.equal(f.record.data.sab_offer_release_state, 'draft');
    assert.equal(saves, 0);
    await f.render(); assert.equal(f.calls.length, 1);
});

test('first save of a new order is detected after real id is assigned', async () => {
    const f = fixture(); f.record.resId=false; f.record.dirty=true;
    f.panel._savedPositionKey=f.panel.savedPositionKey();
    putLine(f.record, 0); await f.render(); assert.equal(f.calls.length,0);
    f.record.resId=300; f.record.dirty=false; putLine(f.record,301);
    await f.render();
    assert.equal(f.calls.length,1);
    assert.equal(f.calls[0][2][0][0],300);
});

test('material-workspace changes also refresh after saving', async () => {
    const f=fixture(); await f.render();
    f.record.dirty=true; putLine(f.record,0,'NTG 1','sab_material_calculation_line_ids');
    await f.render(); assert.equal(f.calls.length,0);
    f.record.dirty=false; putLine(f.record,201,'NTG 1','sab_material_calculation_line_ids');
    await f.render(); assert.equal(f.calls.length,1);
});

test('deleting the last position refreshes the saved empty list', async () => {
    const f=fixture(); putLine(f.record,101); f.panel._savedPositionKey=f.panel.savedPositionKey();
    await f.render(); f.record.dirty=true; f.record.data.sab_calculation_line_ids.records=[];
    await f.render(); assert.equal(f.calls.length,0);
    f.record.dirty=false; f.record.data.write_date='t2'; await f.render();
    assert.equal(f.calls.length,1);
});

test('a slower old request cannot overwrite the newest payload', async () => {
    const f=fixture(); const resolves=[];
    f.panel.orm.call = () => new Promise(resolve => resolves.push(resolve));
    const old=f.panel.loadPayload(); const newest=f.panel.loadPayload();
    resolves[1]({lv_positions:[{position:'1.1.1'}]}); await newest;
    resolves[0]({lv_positions:[]}); await old;
    assert.equal(f.panel.state.payload.lv_positions[0].position,'1.1.1');
    assert.equal(f.panel.state.loading,false);
});

test('late response after unmount does not change the component', async () => {
    const f=fixture(); let resolve;
    f.panel.orm.call=()=>new Promise(r=>{resolve=r;});
    const pending=f.panel.loadPayload();
    f.unmount.forEach(callback=>callback());
    resolve({lv_positions:[{position:'old'}]}); await pending;
    assert.equal(f.panel.state.payload.lv_positions.length,0);
});

test('unsaved order does not query backend or create any record', async () => {
    const f=fixture(); f.record.resId=false;
    await f.panel.loadPayload();
    assert.equal(f.calls.length,0);
    assert.equal(f.panel.state.payload.lv_positions.length,0);
});
