#!/usr/bin/env python3
"""Make a self-contained offline polygon picker; no photo upload."""
import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys

from PIL import Image


def create(data):
    source = Path(data['image']).resolve()
    output = Path(data['output_dir']).resolve()/'water-mask-editor.html'
    if output.exists() and data.get('overwrite') is not True:
        raise ValueError('Picker already exists; use overwrite only when authorized.')
    if output.resolve() == source or output.is_symlink():
        raise ValueError('Output must not overwrite input.')
    with Image.open(source) as opened:
        image = opened.convert('RGB')
    if image.width*4 != image.height*3:
        raise ValueError('Expected a 3:4 poster.')
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    template = (Path(__file__).resolve().parent.parent/'assets/motion-picker.html').read_text(encoding='utf-8')
    template = template.replace('__IMAGE_DATA__', base64.b64encode(buffer.getvalue()).decode('ascii'))
    template = template.replace('__IMAGE_WIDTH__', str(image.width)).replace('__IMAGE_HEIGHT__', str(image.height))
    template = template.replace('__IMAGE_SHA256__', hashlib.sha256(source.read_bytes()).hexdigest())
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(template,encoding='utf-8')
    return {'editor': str(output), 'offline': True,
            'next': 'Open this HTML locally; outline water and exclusions, draw flow direction, and save both exported files beside the poster.'}


def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data,dict): raise ValueError('stdin must be a JSON object.')
        result = {'ok':True,'result':create(data)}
    except (ValueError,KeyError,TypeError,OSError) as error:
        result = {'ok':False,'code':'PICKER_INPUT_ERROR','message':str(error)}
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['ok'] else 1


if __name__=='__main__':
    sys.exit(main())
