(() => {
    const form = document.getElementById('demand-calculator');
    if (!form) return;

    const fields = ['volume', 'share', 'energy', 'loading'].map(name => form.elements.namedItem(name));
    const results = document.getElementById('calculator-results');
    const error = document.getElementById('calculator-error');
    const outputs = ['demand-tonnes', 'demand-per-car', 'demand-cars', 'demand-energy']
        .map(id => document.getElementById(id));
    const number = new Intl.NumberFormat('ru-RU', { maximumSignificantDigits: 8 });

    function update() {
        let valid = true;
        fields.forEach(field => {
            const invalid = !field.validity.valid || !Number.isFinite(field.valueAsNumber);
            field.setAttribute('aria-invalid', String(invalid));
            if (invalid) valid = false;
        });

        const [volume, share, energy, loading] = fields.map(field => field.valueAsNumber);
        const cars = volume * 1e6 * share / 100;
        const perCar = energy * loading;
        const batteryEnergy = cars * energy / 1e6;
        const tonnes = batteryEnergy * loading;
        const values = [tonnes, perCar, cars, batteryEnergy];
        const finite = values.every(Number.isFinite);

        error.hidden = valid && finite;
        results.hidden = !valid || !finite;
        if (!valid) {
            error.textContent = 'Заполните все поля числами не меньше нуля. Доля технологии должна быть от 0 до 100%.';
        } else if (!finite) {
            error.textContent = 'Значения слишком велики для расчёта. Уменьшите исходные параметры.';
        } else {
            error.textContent = '';
            outputs.forEach((output, index) => { output.textContent = number.format(values[index]); });
        }
    }

    form.addEventListener('input', update);
    form.addEventListener('submit', event => { event.preventDefault(); update(); });
    form.addEventListener('reset', () => { setTimeout(update, 0); });
    update();
})();
