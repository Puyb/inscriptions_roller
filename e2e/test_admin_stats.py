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
    assert datasets(admin_page) == ['e2e']


def test_url_hash_selects_settings_and_courses(admin_page):
    admin_page.goto(URL + '#align=start&data=equipes&course=e2e&course=e2estats')
    expect(admin_page.locator('[name=align][value=start]')).to_be_checked()
    expect(admin_page.locator('[name=data][value=equipes]')).to_be_checked()
    admin_page.wait_for_function("window.Chart && Object.keys(Chart.instances).length === 1")
    admin_page.wait_for_function(LAST + ".data.datasets.length >= 2")
    assert datasets(admin_page)[:2] == ['e2e', 'e2estats']


def test_adding_a_course_redraws_and_updates_the_hash(admin_page):
    admin_page.goto(URL)
    admin_page.wait_for_function("window.Chart && Object.keys(Chart.instances).length === 1")
    admin_page.select_option('#add_course', 'e2estats')
    admin_page.wait_for_function(LAST + ".data.datasets.length >= 2")
    assert 'e2estats' in datasets(admin_page)
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
