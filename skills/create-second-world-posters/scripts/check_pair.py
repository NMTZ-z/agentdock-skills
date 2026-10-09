#!/usr/bin/env python3
"""Validate an image/video pair and optional unchanged image regions."""
import argparse
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageChops


def check(args):
    image_path, video_path = Path(args.image), Path(args.video)
    assert image_path.is_file() and video_path.is_file(), 'Missing deliverable'
    with Image.open(image_path) as opened:
        assert opened.format == 'PNG', 'Expected PNG delivery'
        im = opened.convert('RGB')
        im.load()
    width, height = im.size
    assert width * 4 == height * 3, 'Expected width:height 3:4'
    result = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(video_path)
    ]))
    videos = [s for s in result['streams'] if s['codec_type'] == 'video']
    assert len(videos) == 1, 'Expected one video stream'
    assert not any(s['codec_type'] == 'audio' for s in result['streams']), 'Expected no audio'
    stream = videos[0]
    assert (stream['width'], stream['height']) == (width, height), 'Image/video dimensions differ'
    assert stream['codec_name'] == 'h264', 'Expected H.264'
    assert stream['r_frame_rate'] == '24/1', 'Expected 24 fps'
    assert int(stream['nb_frames']) == 72, 'Expected 72 frames'
    assert abs(float(stream['duration']) - 3) < 0.000001, 'Expected exactly three seconds'
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(video_path), '-f', 'null', '-'], check=True)
    if args.unchanged_box:
        assert args.before, 'Supply --before for unchanged-region checks'
        with Image.open(args.before) as original:
            before = original.convert('RGB')
        assert before.size == im.size, 'Before/after dimensions differ'
        for text in args.unchanged_box:
            box = tuple(int(item) for item in text.split(','))
            assert len(box) == 4 and 0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height, 'Invalid box'
            assert ImageChops.difference(before.crop(box), im.crop(box)).getbbox() is None, f'Protected region changed: {box}'
    print(json.dumps({'status': 'PASS', 'image': str(image_path), 'video': str(video_path),
                      'size': [width, height], 'duration': 3, 'frames': 72,
                      'protected_regions_checked': len(args.unchanged_box)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('video')
    parser.add_argument('--before')
    parser.add_argument('--unchanged-box', action='append', default=[])
    check(parser.parse_args())
