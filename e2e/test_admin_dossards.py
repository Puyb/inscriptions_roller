"""Pick-up desk listing (`admin/listing_dossards_form.html`): a colResizable
slider splits the bib numbers between N desks."""
import re

from playwright.sync_api import expect

URL = '/course/listing/dossards/'


def lines(page):
    rows = page.locator('#lines tr')
    return [rows.nth(i).locator('td').first.inner_text() for i in range(rows.count())]


def total(page):
    return sum(int(re.match(r'(\d+)', t).group(1)) for t in lines(page))


def test_single_desk_by_default_holds_every_bib(admin_page):
    admin_page.goto(URL)
    assert len(lines(admin_page)) == 1
    assert total(admin_page) > 0
    expect(admin_page.locator('[name=split]')).to_have_value(re.compile(r'^\d+$'))


def test_more_desks_split_the_bibs_without_losing_any(admin_page):
    admin_page.goto(URL)
    everything = total(admin_page)
    admin_page.fill('#number', '3')
    admin_page.locator('#number').dispatch_event('change')
    expect(admin_page.locator('#range td')).to_have_count(3)
    assert len(lines(admin_page)) == 3
    assert total(admin_page) == everything
    # one split point per desk boundary: "n1,n2,n3"
    assert len(admin_page.locator('[name=split]').input_value().split(',')) == 3


def test_dragging_a_grip_moves_bibs_between_desks(admin_page):
    admin_page.goto(URL)
    admin_page.fill('#number', '2')
    admin_page.locator('#number').dispatch_event('change')
    before = [int(re.match(r'(\d+)', t).group(1)) for t in lines(admin_page)]
    grip = admin_page.locator('.JCLRgrip').first
    box = grip.bounding_box()
    admin_page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    admin_page.mouse.down()
    admin_page.mouse.move(box['x'] + 120, box['y'] + box['height'] / 2, steps=8)
    admin_page.mouse.up()
    after = [int(re.match(r'(\d+)', t).group(1)) for t in lines(admin_page)]
    assert sum(after) == sum(before)
    assert after[0] > before[0]


def test_generate_prints_one_section_per_desk(admin_page):
    admin_page.goto(URL)
    admin_page.fill('#number', '2')
    admin_page.locator('#number').dispatch_event('change')
    admin_page.get_by_role('button', name='Générer').click()
    expect(admin_page.locator('body')).to_contain_text(re.compile(r'\d+ à \d+'))
