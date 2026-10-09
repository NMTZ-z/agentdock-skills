#!/usr/bin/env python3
"""Flag imperceptible motion at phone size; metrics do not replace visual inspection."""
import argparse
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw


def audit(args):
    width = args.width
    assert width > 0 and width % 3 == 0, 'Preview width must be a positive multiple of 3'
    height = width * 4 // 3
    roi = [float(item) for item in args.roi.split(',')]
    assert len(roi) == 4 and 0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1
    raw = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(Path(args.video)), '-vf', f'scale={width}:{height},fps=24',
        '-frames:v', '72', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'
    ])
    frames = np.frombuffer(raw, np.uint8).reshape(-1, height, width, 3)
    assert len(frames) == 72, 'Expected three seconds at 24 fps'
    x0, y0, x1, y1 = int(roi[0]*width), int(roi[1]*height), int(roi[2]*width), int(roi[3]*height)
    region = frames[:, y0:y1, x0:x1].astype(np.int16)
    difference = np.abs(region-region[0]).max(axis=-1)
    means = difference.mean(axis=(1, 2))
    best = int(np.argmax(means))
    changed = float((difference[best] > 12).mean())
    result = {'video': str(Path(args.video)), 'preview': [width, height], 'roi': roi,
              'largest_change_seconds': best/24, 'mean_max_channel_difference': float(means[best]),
              'roi_fraction_changed_over_12': changed,
              'suspect_nearly_static': float(means[best]) < 2 or changed < .01,
              'note': 'RGB changes include compression and exposure; inspect visible directional movement and anchors.'}
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.qa:
        canvas = Image.new('RGB', (width*2, height+30), '#f7f1e4')
        canvas.paste(Image.fromarray(frames[0]), (0, 30))
        canvas.paste(Image.fromarray(frames[best]), (width, 30))
        draw = ImageDraw.Draw(canvas)
        draw.text((6, 6), '0s', fill='black')
        draw.text((width+6, 6), f'{best/24:.3f}s', fill='black')
        path = Path(args.qa)
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(path)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video')
    parser.add_argument('--width', type=int, default=390)
    parser.add_argument('--roi', default='0,0.55,1,0.95', help='Normalized main moving-object area')
    parser.add_argument('--report')
    parser.add_argument('--qa')
    audit(parser.parse_args())
