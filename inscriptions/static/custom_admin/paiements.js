const load = async function() {
    try {
        if (document.querySelectorAll('.column-montant').length) {
            const res = await fetch(location.href.split('?').join('total/?'));
            const data = await res.json();
            document.querySelectorAll('.column-montant a')[0].innerHTML += ` (${data.montant} €)`;
            document.querySelectorAll('.column-montant_frais a')[0].innerHTML += ` (${data.montant_frais} €)`;
        }
    } catch (err) {
        console.error(err);
    }
};
document.onload = load;

