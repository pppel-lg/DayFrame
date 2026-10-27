"""Opt-in browser acceptance against a disposable running Dayframe instance.

Install playwright and its Chromium, start the app with isolated data, then run.
This writes synthetic test records. Never aim it at your personal archive.
"""
import argparse
import io
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8765')
    parser.add_argument('--output', default='artifacts/browser')
    options = parser.parse_args()
    output = Path(options.output)
    output.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    Image.new('RGB', (360, 450), '#c9d8ce').save(buffer, 'PNG')
    imported = buffer.getvalue()
    day = date.today().isoformat()
    errors, failures = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        context = browser.new_context(viewport={'width': 1505, 'height': 1045}, permissions=['camera'])
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('response', lambda response: failures.append(f'{response.status} {response.url}') if response.status >= 500 else None)
        page.on('dialog', lambda dialog: dialog.accept())
        page.goto(options.base)
        expect(page.get_by_role('heading', name='留下今天的一帧')).to_be_visible()
        page.screenshot(path=str(output / 'today-empty.png'), full_page=True)
        page.get_by_label('想对自己说', exact=True).fill('Browser acceptance diary · 浏览器验收')
        page.get_by_label('所在城市').fill('台北')
        page.get_by_label('标签').fill('验收, synthetic')
        page.get_by_title('平静', exact=True).click()
        page.get_by_role('button', name='开启相机', exact=True).click()
        expect(page.locator('video')).to_be_visible()
        page.wait_for_function('document.querySelector("video")?.videoWidth > 0')
        page.get_by_role('button', name='拍下今天', exact=True).click()
        expect(page.get_by_alt_text('刚刚拍摄的照片，尚未保存')).to_be_visible()
        page.get_by_role('button', name='保存今天的一帧', exact=True).click()
        expect(page.get_by_role('status').filter(has_text='已经好好保存')).to_be_visible()
        response = context.request.get(options.base + f'/api/entries/{day}')
        entry = response.json()
        assert entry['note'] == 'Browser acceptance diary · 浏览器验收', entry
        assert entry['photos'][0]['source'] == 'camera' and entry['photos'][0]['captured_at_utc']
        first_primary = entry['primary_photo_id']
        page.locator('input[type=file]').set_input_files({'name': 'synthetic.png', 'mimeType': 'image/png', 'buffer': imported})
        expect(page.get_by_role('status').filter(has_text='已经好好保存')).to_be_visible()
        for _ in range(60):
            entry = context.request.get(options.base + f'/api/entries/{day}').json()
            if len(entry['photos']) == 2:
                break
            time.sleep(.1)
        assert len(entry['photos']) == 2 and entry['primary_photo_id'] == first_primary
        imported_photo = next(p for p in entry['photos'] if p['photo_id'] != first_primary)
        assert context.request.get(options.base + f"/api/photos/{imported_photo['photo_id']}?download=true").body() == imported
        page.get_by_role('button', name='管理今日照片', exact=True).click()
        dialog = page.get_by_role('dialog')
        expect(dialog).to_be_visible()
        dialog.get_by_role('button', name='设为主照片', exact=True).click()
        expect(dialog.get_by_role('status')).to_contain_text('主照片已更新')
        assert context.request.get(options.base + f'/api/entries/{day}').json()['primary_photo_id'] == imported_photo['photo_id']
        dialog.get_by_role('button', name='关闭', exact=True).click()
        page.reload()
        expect(page.get_by_label('想对自己说', exact=True)).to_have_value('Browser acceptance diary · 浏览器验收')
        page.screenshot(path=str(output / 'today-saved.png'), full_page=True)
        for route in ['calendar', 'timeline', 'memories', 'locations', 'report', 'settings']:
            page.goto(options.base + '/#' + route)
            expect(page.locator('main h1')).to_be_visible()
            expect(page.locator('.loading')).to_have_count(0)
            page.screenshot(path=str(output / f'{route}.png'), full_page=True)
        page.goto(options.base + '/#letters')
        page.get_by_role('button', name='写一封信', exact=True).click()
        dialog = page.get_by_role('dialog')
        dialog.get_by_label('信件标题').fill('验收未来信')
        dialog.get_by_label('想对未来的自己说').fill('Private future text from browser acceptance')
        dialog.get_by_label('开启日期').fill((date.today()+timedelta(days=30)).isoformat())
        dialog.get_by_role('button', name='封好，寄给未来', exact=True).click()
        expect(page.get_by_role('button').filter(has_text='验收未来信')).to_be_disabled()
        assert 'Private future text' not in page.locator('body').inner_text()
        page.goto(options.base + '/#settings')
        page.get_by_role('button', name='立即备份', exact=True).click()
        expect(page.locator('.job-row').filter(has_text='独立备份').get_by_text('已完成', exact=True)).to_be_visible(timeout=30000)
        expect(page.get_by_label('选择备份')).to_be_visible()
        page.get_by_label('选择备份').select_option(index=1)
        page.get_by_label('新目录名称').fill('browser-restored')
        page.get_by_role('button', name='恢复到新目录', exact=True).click()
        expect(page.get_by_text('备份已恢复到新目录。请核对后手动切换归档挂载。')).to_be_visible(timeout=30000)
        mobile = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, device_scale_factor=1)
        phone = mobile.new_page()
        for route in ['today', 'calendar', 'settings']:
            phone.goto(options.base + '/#' + route)
            expect(phone.locator('main h1')).to_be_visible()
            phone.screenshot(path=str(output / f'mobile-{route}.png'), full_page=True)
            assert phone.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'mobile overflow {route}'
        mobile.close()
        denied = browser.new_context(viewport={'width': 1280, 'height': 900})
        denied.add_init_script("navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('Test permission denied', 'NotAllowedError'))")
        denied_page = denied.new_page()
        denied_page.goto(options.base)
        denied_page.get_by_role('button', name='再拍一张', exact=True).click()
        expect(denied_page.get_by_role('alert')).to_contain_text('摄像头权限未开启')
        fallback = io.BytesIO()
        Image.new('RGB', (90, 100), '#be907d').save(fallback, 'PNG')
        denied_page.locator('input[type=file]').set_input_files({'name': 'permission-fallback.png', 'mimeType': 'image/png', 'buffer': fallback.getvalue()})
        expect(denied_page.get_by_role('status').filter(has_text='已经好好保存')).to_be_visible()
        assert len(denied.request.get(options.base + f'/api/entries/{day}').json()['photos']) == 3
        denied.close()
        rollover = browser.new_context(viewport={'width': 1280, 'height': 900}, timezone_id='Asia/Taipei')
        rollover_page = rollover.new_page()
        current = date.today()
        rollover_page.clock.install(time=datetime(current.year, current.month, current.day, 23, 59, 30, tzinfo=timezone(timedelta(hours=8))))
        rollover_page.goto(options.base)
        expect(rollover_page.get_by_label('想对自己说', exact=True)).to_have_value('Browser acceptance diary · 浏览器验收')
        rollover_page.clock.fast_forward(90000)
        expect(rollover_page.get_by_text('尚未记录', exact=True)).to_be_visible()
        expect(rollover_page.get_by_label('想对自己说', exact=True)).to_have_value('')
        rollover.close()
        assert not errors, errors
        assert not failures, failures
        browser.close()
    result = {'result': 'PASS', 'camera': 'synthetic browser device; simulated denied permission', 'workflow': ['camera capture', 'diary/mood/city/tags', 'original-byte import', 'additional-photo primary retained', 'confirmed primary replacement', 'reload persistence', 'all navigation surfaces', 'future letter hidden', 'backup', 'restore new target', '390px mobile layouts', 'permission-denied file-import fallback', 'midnight date rollover'], 'page_errors': errors, 'server_errors': failures}
    (output/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
