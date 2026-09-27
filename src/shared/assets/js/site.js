(() => {
    const b = document.querySelector('.menu-toggle');
    const n = document.querySelector('.main-nav');

    if (b && n) {
        b.addEventListener('click', () => {
            const o = n.classList.toggle('open');
            b.setAttribute('aria-expanded', String(o));
            b.setAttribute('aria-label', o ? b.dataset.labelClose : b.dataset.labelOpen);
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && n.classList.contains('open')) {
                n.classList.remove('open');
                b.setAttribute('aria-expanded', 'false');
                b.setAttribute('aria-label', b.dataset.labelOpen);
                b.focus();
            }
        });
    }

    const section = document.body?.dataset.section;
    if (section) {
        document.querySelectorAll('.main-nav .nav-link[data-section]').forEach(link => {
            const active = link.dataset.section === section;
            link.classList.toggle('active', active);
            if (active) {
                link.setAttribute('aria-current', 'page');
            } else {
                link.removeAttribute('aria-current');
            }
        });
    }

    document.querySelectorAll('[data-current-year]').forEach(
        e => e.textContent = new Date().getFullYear()
    );

    const fs = document.querySelectorAll('[data-filter]');
    const items = document.querySelectorAll('.filterable');
    fs.forEach(f => f.addEventListener('click', () => {
        fs.forEach(x => x.classList.remove('active'));
        f.classList.add('active');
        const v = f.dataset.filter;
        items.forEach(i => {
            i.hidden = v !== 'all' && !(i.dataset.category || '').split(' ').includes(v);
        });
    }));

})();
