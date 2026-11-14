"""Public stats pages: `/<uid>/stats/` (Bluff + Leaflet, inline scripts) and
`/<uid>/stats/<uid2>` (Chart.js). Every script must run without a JS error, with
and without geocoded teams (the geocoding reference is the local `CodePostal` table)."""
from playwright.sync_api import expect

GEO = '/e2estats/e2estats/stats/'
NOGEO = '/e2enogeo/e2enogeo/stats/'


def watch(page):
    """Collect page errors and console errors (network failures of third-party
    tiles/CDN are not ours to judge)."""
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error'
            and 'Failed to load resource' not in m.text else None)
    return errors


def test_geocoded_course_shows_map_tables_and_charts(page):
    errors = watch(page)
    page.goto(GEO)
    page.wait_for_load_state('networkidle')
    expect(page.locator('#map')).to_be_visible()
    expect(page.locator('#no-map')).to_have_count(0)
    assert page.locator('.leaflet-marker-icon').count() >= 2  # Troyes, Bruxelles
    for canvas in ('canvas_pays', 'canvas_clubs', 'canvas_categories', 'canvas_distance', 'canvas_time'):
        expect(page.locator('#' + canvas)).to_have_count(1)
    html = page.content()
    assert 'Grand-Est' in html and 'Non localisé' in html
    assert 'flags/.png' not in html
    # the city table counts team managers' cities weighted by team size
    assert page.locator('td', has_text='Troyes').count() >= 1
    assert errors == []


def test_course_without_known_city_degrades_gracefully(page):
    errors = watch(page)
    page.goto(NOGEO)
    page.wait_for_load_state('networkidle')
    expect(page.locator('#no-map')).to_be_visible()
    expect(page.locator('#map')).to_have_count(0)
    expect(page.locator('#canvas_distance')).to_have_count(0)
    expect(page.locator('#canvas_pays')).to_have_count(1)
    assert 'Non localisé' in page.content()
    assert errors == []


def test_payment_charts_are_for_staff_only(page, super_page):
    errors = watch(page)
    page.goto(GEO)
    page.wait_for_load_state('networkidle')
    expect(page.locator('#canvas_paiement')).to_have_count(0)
    assert errors == []

    errors = watch(super_page)
    super_page.goto(GEO)
    super_page.wait_for_load_state('networkidle')
    for canvas in ('canvas_paiement', 'canvas_documents', 'canvas_licencies'):
        expect(super_page.locator('#' + canvas)).to_have_count(1)
    assert errors == []


def test_compare_page_aligns_on_the_nth_price_change(page):
    errors = watch(page)
    page.goto('/e2estats/e2estats/stats/e2e/e2e?align=augment%3A2&data=equipes')
    page.wait_for_function("window.Chart && Object.keys(Chart.instances).length === 1")
    assert page.evaluate("Object.values(Chart.instances)[0].data.datasets.map(d => d.label)") == ['e2estats/e2estats', 'e2e/e2e']
    # menu: one entry per price change (the compared courses have 3 and 1)
    values = page.evaluate("[...document.querySelectorAll('[data-name=align]')].map(a => a.dataset.value)")
    assert values == ['', 'augment', 'augment:2', 'augment:3', 'start']
    assert errors == []
