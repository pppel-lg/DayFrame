"""Targeted UI regression checks against browser-smoke's disposable instance."""
import io
import json
from datetime import date, timedelta
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright


def main():
    base = 'http://127.0.0.1:8765'
    today = date.today().isoformat()
    previous = (date.today()-timedelta(days=1)).isoformat()
    image = io.BytesIO()
    Image.new('RGB', (360, 450), '#c9d8ce').save(image, 'PNG')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        page = context.new_page()
        confirmations = []
        def confirm(dialog):
            confirmations.append(dialog.message)
            dialog.accept()
        page.on('dialog', confirm)
        while context.request.get(base+f'/api/entries/{previous}').status == 200:
            previous = (date.fromisoformat(previous)-timedelta(days=1)).isoformat()
        page.goto(base + '/#calendar')
        page.locator(f'button[title^="{previous} "]').click()
        dialog = page.get_by_role('dialog')
        expect(dialog).to_be_visible()
        dialog.locator('input[type=file]').set_input_files({'name': 'cross-date.png', 'mimeType': 'image/png', 'buffer': image.getvalue()})
        expect(dialog.get_by_role('status')).to_contain_text('照片已保存')
        assert any('相同原图已存在于其他日期' in message for message in confirmations), confirmations
        assert context.request.get(base+f'/api/entries/{previous}').json()['status'] == 'recorded'
        dialog.get_by_role('button', name='关闭', exact=True).click()
        page.goto(base + '/#settings')
        page.get_by_role('button', name='导出 CSV 与离线日历', exact=True).click()
        expect(page.get_by_role('link', name='下载 CSV 数据', exact=True)).to_be_visible(timeout=30000)
        # Simulate a missing original at the API boundary without deleting a file.
        missing_context = browser.new_context(viewport={'width': 1280, 'height': 900})
        def missing_response(route):
            response = route.fetch()
            if response.status != 200:
                return route.fulfill(response=response)
            payload = response.json()
            entries = payload.get('entries', []) if isinstance(payload, dict) else []
            if isinstance(payload, dict) and 'record_date' in payload:
                entries = [payload]
            for entry in entries:
                for photo in entry.get('photos', []):
                    photo['missing'] = True
            route.fulfill(response=response, json=payload)
        missing_context.route('**/api/entries**', missing_response)
        missing_page = missing_context.new_page()
        missing_page.goto(base)
        expect(missing_page.get_by_text('原图缺失，待恢复', exact=True)).to_be_visible()
        assert not missing_page.locator('.today-state').evaluate("el => el.classList.contains('complete')")
        missing_page.goto(base + '/#calendar')
        expect(missing_page.locator(f'button[title="{today} 原图缺失，待恢复"]')).to_be_visible()
        assert missing_page.locator(f'button[title="{today} 原图缺失，待恢复"]').evaluate("el => !el.classList.contains('recorded')")
        missing_context.close()
        browser.close()
    result = {'result': 'PASS', 'checks': ['cross-date duplicate explicit confirmation', 'CSV download link', 'missing original warning and no completed day/heatmap state']}
    Path('artifacts/browser/edge-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
