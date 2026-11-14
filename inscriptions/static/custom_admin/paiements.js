// sortable headers wrap their label in a link, the others in a span
const label = column => {
    const th = document.querySelector('th.column-' + column);
    return th && (th.querySelector('a') || th.querySelector('.text span') || th);
};

const load = async function() {
    try {
        if (document.querySelectorAll('.column-montant').length) {
            // keep the active filters (?type=...) and always hit `total/`
            const url = new URL('total/', location.href);
            url.search = location.search;
            const res = await fetch(url);
            const data = await res.json();
            label('montant').innerHTML += ` (${data.montant} €)`;
            label('montant_frais2').innerHTML += ` (${data.montant_frais} €)`;
        }
    } catch (err) {
        console.error(err);
    }
};
if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', load);
else
    load();
