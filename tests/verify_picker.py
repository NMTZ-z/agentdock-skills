"""Optional real browser check, outside unittest discovery. Requires Playwright."""
import argparse
from pathlib import Path
import json
import subprocess
import sys
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--image',required=True);p.add_argument('--out',required=True);args=p.parse_args()
job=Path(args.out).resolve();job.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,'-B',str(ROOT/'quickstart.py'),'select',args.image,'--out',str(job),'--overwrite'],check=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(accept_downloads=True,viewport={'width':1300,'height':1200})
    failures=[];requests=[]
    page.on('pageerror',lambda error:failures.append(str(error)))
    page.on('request',lambda request:requests.append(request.url))
    page.goto((job/'water-mask-editor.html').as_uri())
    page.wait_for_function('source.complete && source.naturalWidth > 0')
    assert page.locator('#config').is_disabled()
    w,h=page.evaluate('[W,H]')
    def point(x,y):
        box=page.locator('#view').bounding_box()
        page.mouse.click(box['x']+x/w*box['width'],box['y']+y/h*box['height'])
    def shape(points):
        for x,y in points:point(x*w,y*h)
        page.locator('#finish').click()
    shape([(.03,.36),(.96,.36),(.96,.42),(.60,.475),(.17,.475),(.03,.46)])
    page.locator('#mode').select_option('protect')
    shape([(.43,.39),(.49,.39),(.49,.43),(.43,.43)])
    page.locator('#showmask').check()
    assert page.evaluate('maskCanvas().getContext("2d").getImageData(W*.46,H*.41,1,1).data[0]')==0
    assert page.evaluate('maskCanvas().getContext("2d").getImageData(W*.3,H*.4,1,1).data[0]')==255
    page.locator('#undo').click()  # Remove synthetic exclusion; public sample has no invented fixed island.
    page.locator('#showmask').uncheck()
    page.locator('#mode').select_option('flow')
    point(.24*w,.40*h);point(.72*w,.42*h)
    assert page.locator('#config').is_enabled()
    for button,name in [('mask','water_mask.png'),('config','motion.json')]:
        with page.expect_download() as info:page.locator('#'+button).click()
        info.value.save_as(job/name)
    # An unfinished polygon cannot silently disappear into an export.
    page.locator('#mode').select_option('water');point(.3*w,.4*h)
    assert page.locator('#config').is_disabled()
    page.locator('#undo').click();assert page.locator('#config').is_enabled()
    page.screenshot(path=str(job/'picker-qa.png'),full_page=True)
    assert not failures,failures
    assert not [url for url in requests if url.startswith(('http:','https:'))],requests
    with Image.open(job/'water_mask.png') as mask:
        assert mask.size==(w,h);assert mask.convert('L').getpixel((0,0))==0
    config=json.loads((job/'motion.json').read_text());assert config['water_mask']=='water_mask.png'
    print(json.dumps({'ok':True,'browser':'Chromium','downloads':2,'external_requests':0,'mask_size':[w,h],'draft_guard':True}))
    browser.close()
