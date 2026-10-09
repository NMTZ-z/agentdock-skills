#!/usr/bin/env python3
"""Optional SenseNova image editor, with source pixels restored after generation."""
import base64
from io import BytesIO
import json
import math
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image, ImageOps


class PosterError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, code, message):
    if not condition:
        raise PosterError(code, message)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def service_settings():
    key = os.environ.get('SENSENOVA_API_KEY', '')
    base = os.environ.get('SENSENOVA_BASE_URL', 'https://token.sensenova.cn/v1').rstrip('/')
    model = os.environ.get('SENSENOVA_IMAGE_MODEL', 'sensenova-u1.5-lite')
    timeout = float(os.environ.get('SENSENOVA_TIMEOUT_SECONDS', '180'))
    parsed = urllib.parse.urlsplit(base)
    require(bool(key), 'MISSING_API_KEY', 'Set SENSENOVA_API_KEY in the process environment; never pass it in JSON.')
    require(not parsed.username and not parsed.password and not parsed.query and not parsed.fragment,
            'INVALID_SERVICE_URL', 'Service URL must not contain credentials, a query or a fragment.')
    require(parsed.scheme == 'https' or (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')),
            'INVALID_SERVICE_URL', 'Use HTTPS; HTTP is allowed only for an explicitly configured loopback test service.')
    require(bool(parsed.hostname) and parsed.path.endswith('/v1'), 'INVALID_SERVICE_URL', 'Base URL must end with /v1.')
    require(math.isfinite(timeout) and 1 <= timeout <= 600, 'INVALID_TIMEOUT', 'Timeout must be 1–600 seconds.')
    require(bool(model.strip()), 'INVALID_MODEL', 'SENSENOVA_IMAGE_MODEL must be nonempty.')
    return key, base, model, timeout


def prepare_canvas(image_path, width=1152, photo_share=.58, anchor=(.5, 1)):
    require(isinstance(width, int) and not isinstance(width, bool) and width % 96 == 0 and 768 <= width <= 3072,
            'INVALID_SIZE', 'Width must be a multiple of 96 between 768 and 3072; height is width × 4/3.')
    require(math.isfinite(photo_share) and .55 <= photo_share <= .65,
            'INVALID_LAYOUT', 'Photo share must be 0.55–0.65.')
    require(len(anchor) == 2 and all(math.isfinite(float(x)) and 0 <= x <= 1 for x in anchor),
            'INVALID_CROP', 'Crop anchor must contain two normalized coordinates.')
    with Image.open(image_path) as opened:
        image = ImageOps.exif_transpose(opened).convert('RGB')
    height = width*4//3
    cut = round(height*photo_share)
    scale = max(width/image.width, cut/image.height)
    resized = image.resize((round(image.width*scale), round(image.height*scale)), Image.Resampling.LANCZOS)
    left = round((resized.width-width)*anchor[0])
    top = round((resized.height-cut)*anchor[1])
    photo = resized.crop((left, top, left+width, top+cut))
    canvas = Image.new('RGB', (width, height), '#f6efdf')
    canvas.paste(photo, (0, 0))
    crop_fraction = 1-(width*cut)/(resized.width*resized.height)
    report = {'input_size': list(image.size), 'output_size': [width, height], 'photo_rows': cut,
              'photo_share': cut/height, 'cropped_area_fraction': crop_fraction,
              'crop_anchor': list(anchor), 'resampling': 'Lanczos, uniform scaling then crop',
              'preservation': 'Final photo region exactly reuses the prepared scaled/cropped source; not original-resolution losslessness.'}
    return canvas, report


def build_prompt(location, caption, idea, cut, width, height):
    return f'''编辑这张预先排好版的第二世界旅行海报，完整画布 {width}×{height}、宽高3:4。
上方从第0行到第{cut-1}行是实拍照片，下方从第{cut}行开始是象牙色纸面。严格保持分区的位置。
原照片地点由用户提供：{location}。不猜行政区，不杜撰背景或诗句出处。
上方照片绝不重绘、不调色、不替换、不新增或删减主体。成品会重新贴回同一位置的原照片像素。
必须从照片下缘真实到达分界的一条结构继续向下，交点、方向、宽度、色彩和遮挡完全对应；上下读作同一场景。
先连通再改变物理规则，连接结构逐渐成为温暖象牙色纤维纸上的水彩材质和细黑手绘线，大面积留白。
不重画下半整片风景，不做统一撕纸形状，不在纸上另放一个孤立插图；不做样机、边框、徽标、水印或英文。
每张只有一种自然转化、一个具体互动；不重复人物，不为了装饰添加群体。可有0至1个微小黑线人物。
手与物体接触、脚与地面接触、坐姿臀部有干燥承托，受力可信；人不能直接坐在水里。
具体互动意图：{idea or '依据真实连接结构，设计一个可触摸、牵引或使用它的轻巧互动；不要从固定道具倒推。'}
仅在纸面自然留白角落以细小、清楚的中文手写写这一句，逐字准确：{caption}
文字字高约画布宽度的2%，整句占宽不超过35%，不可成为标题。
文字不能遮住连接点和互动，也不能出现在原照片上。整体明亮、通透、克制、自然衔接。'''


def edit_canvas(canvas, prompt):
    key, base, model, timeout = service_settings()
    buffer = BytesIO()
    canvas.save(buffer, format='PNG')
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    payload = {'model': model, 'images': [{'image_url': 'data:image/png;base64,'+encoded}],
               'prompt': prompt, 'n': 1, 'size': f'{canvas.width}x{canvas.height}',
               'output_format': 'png', 'response_format': 'b64_json',
               'watermark': False, 'prompt_extend': False}
    request = urllib.request.Request(base+'/images/edits', data=json.dumps(payload).encode(),
                                    headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'}, method='POST')
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(64*1024*1024+1)
        require(len(body) <= 64*1024*1024, 'RESPONSE_TOO_LARGE', 'Image response exceeds 64 MiB.')
    except urllib.error.HTTPError as error:
        # Never expose service bodies: they can echo credentials or request data.
        code = error.code
        error.close()
        raise PosterError('SERVICE_HTTP_ERROR', f'Image service returned HTTP {code}; check permission, quota and model.') from None
    except (urllib.error.URLError, TimeoutError):
        raise PosterError('SERVICE_UNREACHABLE', 'Image service unavailable or timed out; no automatic retry was made.') from None
    try:
        result = json.loads(body)
        item = result['data'][0]
        raw = base64.b64decode(item['b64_json'], validate=True)
        with Image.open(BytesIO(raw)) as opened:
            generated = opened.convert('RGB')
            generated.load()
    except (ValueError, KeyError, IndexError, TypeError, OSError):
        raise PosterError('INVALID_IMAGE_RESPONSE', 'Service did not return a valid Base64 image.') from None
    require(generated.size == canvas.size, 'IMAGE_SIZE_MISMATCH', 'Service changed canvas dimensions; output was not resized or delivered.')
    return generated, model


def prepare_job(data, require_key=False):
    require(not any(key in data for key in ('api_key', 'token', 'secret')), 'SECRET_IN_INPUT', 'Use process environment for credentials.')
    image_path = Path(data['image']).resolve()
    require(image_path.is_file(), 'MISSING_IMAGE', 'Input photo not found.')
    location = str(data.get('location', '')).strip()
    caption = str(data.get('caption') or location).strip()
    require(bool(location) and len(location) <= 150 and 0 < len(caption) <= 200,
            'INVALID_TEXT', 'Provide a location and a short caption; location is used when no caption is supplied.')
    # Validate credentials before creating task output.
    if require_key:
        service_settings()
    output = Path(data['output_dir']).resolve()
    names = (('poster.png', 'prepared.png', 'generated.png', 'poster_report.json', 'prompt.txt')
             if require_key else ('preview.png', 'layout_report.json', 'edit_prompt.txt'))
    paths = [output/name for name in names]
    require(image_path not in [p.resolve() for p in paths] and not any(p.is_symlink() for p in paths),
            'INPUT_OUTPUT_COLLISION', 'Output must not overwrite the input photo or follow output symlinks.')
    require(not any(p.exists() for p in paths) or data.get('overwrite') is True,
            'OUTPUT_EXISTS', 'Task output already exists; use overwrite only when authorized.')
    canvas, report = prepare_canvas(image_path, data.get('width', 1152),
                                    float(data.get('photo_share', .58)), data.get('crop_anchor', [.5, 1]))
    max_crop = float(data.get('max_crop', .20))
    require(math.isfinite(max_crop) and 0 <= max_crop <= .6, 'INVALID_CROP', 'max_crop must be finite and between 0 and 0.6.')
    require(report['cropped_area_fraction'] <= max_crop,
            'CROP_REVIEW_REQUIRED', 'This layout crops too much source area; inspect it and choose photo_share or crop_anchor before generation.')
    prompt = build_prompt(location, caption, str(data.get('idea', '')), report['photo_rows'], *canvas.size)
    return output, canvas, report, prompt, location, caption


def preview_poster(data):
    output, canvas, report, prompt, _, _ = prepare_job(data)
    output.mkdir(parents=True, exist_ok=True)
    canvas.save(output/'preview.png')
    (output/'layout_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'edit_prompt.txt').write_text(prompt,encoding='utf-8')
    return {'preview':str(output/'preview.png'), 'report':report,
            'next':'Check crop subjects and identify a real structure at the photo bottom before calling poster; no upload occurred.'}


def create_poster(data):
    output, canvas, report, prompt, location, caption = prepare_job(data, require_key=True)
    generated, model = edit_canvas(canvas, prompt)
    final = generated.copy()
    cut = report['photo_rows']
    final.paste(canvas.crop((0, 0, canvas.width, cut)), (0, 0))
    require(final.crop((0, 0, canvas.width, cut)).tobytes() == canvas.crop((0, 0, canvas.width, cut)).tobytes(),
            'PRESERVATION_FAILED', 'Prepared photo region changed.')
    report.update({'model': model, 'location_supplied_by_user': location,
                   'caption': caption, 'preserved_photo_max_difference': 0,
                   'visual_review_required': ['connection alignment', 'caption', 'figure support', 'crop subjects']})
    output.mkdir(parents=True, exist_ok=True)
    final.save(output/'poster.png')
    canvas.save(output/'prepared.png')
    generated.save(output/'generated.png')
    (output/'poster_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'prompt.txt').write_text(prompt,encoding='utf-8')
    return {'poster': str(output/'poster.png'), 'report': report,
            'next': 'Inspect the connection, caption and crop; then select an explicit water mask for video.'}


def main():
    try:
        data = json.load(sys.stdin)
        require(isinstance(data, dict), 'INVALID_INPUT', 'stdin must be a JSON object.')
        worker = preview_poster if data.get('skill_action') == 'prepare' else create_poster
        result = {'ok': True, 'result': worker(data)}
    except PosterError as error:
        result = {'ok': False, 'code': error.code, 'message': str(error)}
    except (ValueError, KeyError, TypeError):
        result = {'ok': False, 'code': 'INVALID_INPUT', 'message': 'Check required image, location, output_dir and numeric options.'}
    except OSError:
        result = {'ok': False, 'code': 'FILE_ERROR', 'message': 'Unable to read or write a task file.'}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
