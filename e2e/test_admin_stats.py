"""Stats page (inline Chart.js script in `admin/stats.html`): chart drawn
from `stats/<uid>/`, settings kept in the URL hash, courses can be added."""
import re

from playwright.sync_api import expect

URL = '/course/stats/'
# the page never destroys old charts (it replaces the canvas): look at the newest
LAST = "Object.values(Chart.instances).slice(-1)[0]"


def datasets(page):
    return page.evaluate(LAST + ".data.datasets.map(d => d.label)")


def test_chart_is_drawn_for_the_current_course(admin_page):
    admin_page.goto(URL)
    expect(admin_page.locator('#canvas_time')).to_be_visible()
    admin_page.wait_for_function("window.Chart && Object.keys(Chart.instances).length === 1")
    assert datasets(admin_page) == ['e2e/e2e']


def test_url_hash_selects_settings_and_courses(admin_page):
    admin_page.goto(URL + '#align=start&data=equipes&course=e2e&course=e2estats')
    expect(admin_page.locator('[name=align][value=start]')).to_be_checked()
    expect(admin_page.locator('[name=data][value=equipes]')).to_be_checked()
    admin_page.wait_for_function("window.Chart && Object.keys(Chart.instances).length === 1")
    admin_page.wait_for_function(LAST + ".data.datasets.length >= 2")
    assert datasets(admin_page)[:2] == ['e2e/e2e', 'e2estats/e2estats']


def test_adding_a_course_redraws_and_updates_the_hash(admin_page):
    admin_page.goto(URL)
    admin_page.wait_for_function("window.Chart && Object.keys(Chart.instances).length === 1")
    admin_page.select_option('#add_course', 'e2estats/e2estats')
    admin_page.wait_for_function(LAST + ".data.datasets.length >= 2")
    assert 'e2estats/e2estats' in datasets(admin_page)
    expect(admin_page.locator('#add_course option[value=e2estats]')).to_have_count(0)
    assert 'course=e2estats' in admin_page.evaluate('location.hash')


def test_changing_a_setting_redraws_and_updates_the_hash(admin_page):
    admin_page.goto(URL)
    admin_page.wait_for_function("window.Chart && Object.keys(Chart.instances).length === 1")
    admin_page.check('[name=data][value=equipiers]')
    admin_page.check('[name=align][value=augmentation]')
    hash_ = admin_page.evaluate('location.hash')
    assert 'data=equipiers' in hash_ and 'align=augmentation' in hash_
    label = admin_page.evaluate(LAST + ".options.scales.yAxes[0].scaleLabel.labelString")
    assert label == 'equipiers'


def wait_chart(page, n_datasets=1):
    page.wait_for_function(
        "window.Chart && Object.keys(Chart.instances).length >= 1 && "
        + LAST + ".data.datasets.length >= %d" % n_datasets)


def lines(page):
    """Vertical annotation lines of the chart, without the grey 'today' marker."""
    return page.evaluate(
        LAST + ".options.annotation.annotations.filter(a => a.borderColor !== 'rgb(127, 127, 127)').length")


def test_one_annotation_per_price_change_date(admin_page):
    # e2e: ouverture/fermeture/course + 1 augmentation ; e2estats: idem + 3 augmentations
    admin_page.goto(URL + '#align=course&data=equipes&course=e2e&course=e2estats')
    wait_chart(admin_page, 2)
    assert lines(admin_page) == 4 + 6


def test_nth_price_change_alignment(admin_page):
    admin_page.goto(URL + '#align=augmentation:2&data=equipes&course=e2e&course=e2estats')
    wait_chart(admin_page, 2)
    expect(admin_page.locator('[name=align][value=augmentation]')).to_be_checked()
    select = admin_page.locator('#augmentation_n')
    expect(select).to_be_visible()
    expect(select.locator('option')).to_have_count(3)
    expect(select).to_have_value('2')
    # picking another one redraws and is kept in the hash
    select.select_option('3')
    admin_page.wait_for_function("location.hash.includes('augmentation')")
    assert 'augmentation%3A3' in admin_page.evaluate('location.hash')
    assert lines(admin_page) == 10


def test_single_price_change_hides_the_selector(admin_page):
    admin_page.goto(URL + '#align=augmentation&data=equipes&course=e2e')
    admin_page.wait_for_function("window.Chart && Object.keys(Chart.instances).length >= 1")
    expect(admin_page.locator('#augmentation_n')).to_be_hidden()
    assert lines(admin_page) == 4


def test_start_alignment_draws_the_curves(admin_page):
    # regression: `delta.start` did not exist, labels were empty (NaN)
    admin_page.goto(URL + '#align=start&data=equipes&course=e2e&course=e2estats')
    wait_chart(admin_page, 2)
    assert admin_page.evaluate(LAST + ".data.labels.length") > 10
