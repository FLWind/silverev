// Exercise the shared calculator with both real source forms and locale messages.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'src/shared/assets/js/demand-calculator.js'), 'utf8');

for (const lang of ['ru', 'en']) {
    const html = fs.readFileSync(path.join(root, `src/${lang}/ev-silver-demand.html`), 'utf8');
    const locale = JSON.parse(fs.readFileSync(path.join(root, `src/${lang}/locale.json`), 'utf8'));
    const names = ['volume', 'share', 'energy', 'loading'];
    const defaults = Object.fromEntries(names.map(name => [name, html.match(new RegExp(`name="${name}"[^>]*value="([^"]+)"`))[1]]));
    const fields = Object.fromEntries(names.map(name => [name, {
        value: defaults[name], attrs: {},
        get valueAsNumber() { return this.value === '' ? NaN : Number(this.value); },
        get validity() { const n = this.valueAsNumber; return {valid: Number.isFinite(n) && n >= 0 && (name !== 'share' || n <= 100)}; },
        setAttribute(key, value) { this.attrs[key] = value; }
    }]));
    const handlers = {};
    const form = {
        elements: {namedItem: name => fields[name]},
        dataset: {invalidMessage: locale.calculator_invalid, overflowMessage: locale.calculator_overflow},
        addEventListener: (name, callback) => { handlers[name] = callback; }
    };
    const nodes = {'demand-calculator': form};
    for (const id of ['calculator-results', 'calculator-error', 'demand-tonnes', 'demand-per-car', 'demand-cars', 'demand-energy']) {
        assert.ok(html.includes(`id="${id}"`), `${lang}: missing calculator element ${id}`);
        nodes[id] = {hidden: false, textContent: ''};
    }
    let pending;
    vm.runInNewContext(source, {
        document: {documentElement: {lang}, getElementById: id => nodes[id]}, Intl, Number,
        setTimeout: callback => { pending = callback; }
    });
    const format = value => new Intl.NumberFormat(lang === 'en' ? 'en-GB' : 'ru-RU', {maximumSignificantDigits: 8}).format(value);
    const set = values => { names.forEach((name, index) => { fields[name].value = String(values[index]); }); handlers.input(); };
    const tonnes = () => nodes['demand-tonnes'].textContent;
    assert.equal(tonnes(), format(187.5));
    assert.equal(nodes['demand-per-car'].textContent, format(375));
    assert.equal(nodes['demand-cars'].textContent, format(500000));
    assert.equal(nodes['demand-energy'].textContent, format(37.5));
    for (const share of [1, 5, 10]) for (const loading of [1, 5, 10]) {
        set([10, share, 75, loading]);
        assert.equal(tonnes(), format(10 * share / 100 * 75 * loading));
    }
    set([10, 100, 75, 5]); assert.equal(tonnes(), format(3750));
    for (let index = 0; index < 4; index++) {
        const values = [10, 5, 75, 5]; values[index] = 0; set(values);
        assert.equal(tonnes(), format(0)); assert.equal(nodes['calculator-results'].hidden, false);
    }
    for (const values of [['', 5, 75, 5], [-1, 5, 75, 5], [10, 101, 75, 5], [10, 5, -75, 5], [10, 5, 75, -5], [10, 'abc', 75, 5]]) {
        set(values);
        assert.equal(nodes['calculator-results'].hidden, true);
        assert.equal(nodes['calculator-error'].textContent, locale.calculator_invalid);
        assert.ok(names.some(name => fields[name].attrs['aria-invalid'] === 'true'));
    }
    set([1e308, 100, 1e308, 1e308]);
    assert.equal(nodes['calculator-error'].textContent, locale.calculator_overflow);
    set([0.1, 0.5, 50, 0.2]); assert.equal(tonnes(), format(0.005));
    handlers.reset(); names.forEach(name => { fields[name].value = defaults[name]; }); pending();
    assert.equal(tonnes(), format(187.5));
    let prevented = false; handlers.submit({preventDefault() { prevented = true; }}); assert.ok(prevented);
    console.log(`${lang}: calculator examples, boundaries, validation, reset and localisation passed`);
}
