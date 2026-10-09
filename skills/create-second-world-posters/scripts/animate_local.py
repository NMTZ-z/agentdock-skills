#!/usr/bin/env python3
"""Create exactly 72 frames of continuous local motion, sampled from one still."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_closing, distance_transform_edt, gaussian_filter, label, map_coordinates

FPS, FRAMES = 24, 72


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def probe(path):
    result = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(path)
    ]))
    video = [s for s in result['streams'] if s['codec_type'] == 'video']
    assert len(video) == 1, 'Expected one video stream'
    assert not any(s['codec_type'] == 'audio' for s in result['streams']), 'Audio found'
    stream = video[0]
    assert stream['r_frame_rate'] == '24/1', 'Expected 24 fps'
    assert int(stream['nb_frames']) == FRAMES, 'Expected 72 frames'
    assert abs(float(stream['duration']) - 3) < 0.000001, 'Expected exactly 3 seconds'
    return stream


def read_mask(path, size, top, bottom, base):
    path = Path(path)
    if not path.is_absolute():
        path = base / path
    with Image.open(path) as im:
        assert im.size == size, f'Mask size mismatch: {path}'
        return np.asarray(im.convert('L'), dtype=np.float32)[top:bottom] / 255


def pair(values, label, positive=False):
    assert len(values) == 2, f'{label} must have two values'
    assert all(math.isfinite(float(v)) for v in values), f'Invalid {label}'
    if positive:
        assert all(float(v) > 0 for v in values), f'{label} must be positive'
    return tuple(float(v) for v in values)


def downstream_field(path, width, height, X, Y):
    """Interpolate downstream direction from the actual river centerline."""
    assert len(path) >= 2, 'Provide at least two centerline points'
    points = np.asarray(path, dtype=np.float32)
    assert points.ndim == 2 and points.shape[1] == 2 and np.isfinite(points).all()
    assert ((points >= 0) & (points <= 1)).all()
    points *= [width, height]
    px, py = X * width, Y * height
    best = np.full_like(X, np.inf)
    vx, vy = np.zeros_like(X), np.zeros_like(X)
    for a, b in zip(points[:-1], points[1:]):
        delta = b - a
        length = float(np.linalg.norm(delta))
        assert length > 0, 'Repeated centerline point'
        u = np.clip(((px-a[0])*delta[0] + (py-a[1])*delta[1]) / length**2, 0, 1)
        d = (px-(a[0]+u*delta[0]))**2 + (py-(a[1]+u*delta[1]))**2
        nearer = d < best
        vx[nearer], vy[nearer] = delta[0]/length, delta[1]/length
        best[nearer] = d[nearer]
    vx, vy = gaussian_filter(vx, 18), gaussian_filter(vy, 18)
    norm = np.maximum(np.hypot(vx, vy), 1e-6)
    return vx / norm, vy / norm


def run(args):
    assert shutil.which('ffmpeg') and shutil.which('ffprobe'), 'Install ffmpeg and ffprobe'
    src_path, destination = Path(args.image).resolve(), Path(args.video).resolve()
    assert src_path != destination, 'Image and video must be different paths'
    if destination.exists() and not args.overwrite:
        raise FileExistsError('Output exists; use --overwrite for an authorized update')
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    assert set(config) <= {'top', 'bottom', 'flow', 'local', 'light', 'protect_mask', 'qa_roi'}, 'Unknown config keys'
    with Image.open(src_path) as opened:
        im = opened.convert('RGB')
        im.load()
    width, height = im.size
    assert width * 4 == height * 3, 'Expected width:height 3:4'
    assert width % 2 == 0 and height % 2 == 0, 'H.264 yuv420p needs even dimensions'
    top_f, bottom_f = float(config.get('top', .35)), float(config.get('bottom', .88))
    assert 0 <= top_f < bottom_f <= 1, 'Invalid motion bounds'
    top, bottom = int(top_f * height), int(bottom_f * height)
    sub = np.asarray(im, dtype=np.float32)[top:bottom]
    yy, xx = np.indices(sub.shape[:2], dtype=np.float32)
    Y, X = (yy + top) / height, xx / width
    movable = np.ones(sub.shape[:2], dtype=np.float32)
    if config.get('protect_mask'):
        movable -= read_mask(config['protect_mask'], im.size, top, bottom, config_path.parent)

    flow = config.get('flow', {})
    mode = flow.get('mode', 'off')
    assert mode in ('water', 'field', 'off'), 'Invalid flow mode'
    method = flow.get('method', 'wave')
    assert method in ('wave', 'advect'), 'Invalid flow method'
    mask = np.zeros_like(X)
    edge_distance = None
    if flow.get('mask'):
        mask = read_mask(flow['mask'], im.size, top, bottom, config_path.parent)
        if method == 'advect':
            edge_distance = distance_transform_edt(mask > 0)
            mask *= smooth(edge_distance / float(flow.get('edge_fade_pixels', 14)))
    elif mode == 'water':
        assert 'start' in flow, 'Set water onset; exclude blue sky'
        start = float(flow['start'])
        assert 0 <= start <= 1
        cyan = smooth((sub[:, :, 2] - sub[:, :, 0] - 10) / 28)
        cyan *= smooth((sub[:, :, 1] - sub[:, :, 0] - 7) / 26)
        if method == 'advect':
            region = binary_closing(cyan > .5, iterations=3)
            holes, count = label(~region)
            sizes = np.bincount(holes.ravel())
            small = sizes < int(flow.get('fill_holes_pixels', 1800))
            small[0] = False
            region |= small[holes]
            # Keep banks and land immobile; do not wobble the whole blue silhouette.
            edge_distance = distance_transform_edt(region)
            mask = smooth(edge_distance / float(flow.get('edge_fade_pixels', 14)))
            mask *= smooth((Y-start) / .04)
        else:
            mask = gaussian_filter(cyan, 2) * smooth((Y - start) / .07)
    elif mode == 'field':
        for field in flow.get('fields', []):
            x0, y0 = pair(field['center'], 'field center')
            wx, wy = pair(field['radius'], 'field radius', positive=True)
            mask += float(field.get('weight', 1)) * np.exp(-((X-x0)/wx)**4 - ((Y-y0)/wy)**4)
    mask = np.clip(mask, 0, 1) * movable
    if method == 'advect':
        # Recompute after protection: source sampling must also avoid protected
        # foreground objects and holes inside the river, not only its banks.
        edge_distance = distance_transform_edt(mask > 0)
    flow_x, flow_y = pair(flow.get('shift', [0, 0]), 'flow shift')
    direction = None
    travel = 0
    if method == 'advect':
        assert mode == 'water', 'Directional advection is for water textures'
        direction = downstream_field(flow['path'], width, height, X, Y)
        travel = float(flow['travel_pixels'])
        assert math.isfinite(travel) and travel > 0, 'Set positive three-second travel'

    fields = []
    for local in config.get('local', []):
        x0, y0 = pair(local['center'], 'local center')
        wx, wy = pair(local['radius'], 'local radius', positive=True)
        shift_x, shift_y = pair(local['shift'], 'local shift')
        fm = np.exp(-((X-x0)/wx)**4 - ((Y-y0)/wy)**4)
        if 'pin_y' in local:
            pin = float(local['pin_y'])
            assert 0 <= pin <= 1
            fm *= 1 - smooth((Y - (pin - .02)) / .02)
        fields.append((fm * movable, shift_x, shift_y))

    estimated_span = travel if direction is not None else 2 * max(abs(flow_x), abs(flow_y))
    for _, ax, ay in fields:
        estimated_span = max(estimated_span, 2 * max(abs(ax), abs(ay)))
    phone_span = estimated_span * 390 / width
    if phone_span < 4 and not args.allow_subtle:
        raise ValueError(f'Primary motion is at most {phone_span:.2f}px at 390px display width. '
                         'Increase meaningful motion; --allow-subtle is only for an explicit nearly-static request.')

    light = config.get('light')
    light_mask, light_amplitude = None, 0
    if light:
        x0, y0 = pair(light['center'], 'light center')
        wx, wy = pair(light['radius'], 'light radius', positive=True)
        light_amplitude = float(light['amplitude'])
        assert 0 <= light_amplitude <= .05, 'Keep light changes within 5%'
        light_mask = np.exp(-((X-x0)/wx)**2 - ((Y-y0)/wy)**2) * movable

    allowed = mask > 0
    for fm, _, _ in fields:
        allowed |= fm > 0
    if light_mask is not None and light_amplitude:
        allowed |= light_mask > 0
    original_tile = np.asarray(im, dtype=np.uint8)[top:bottom]
    protected_max_difference = 0

    roi = config.get('qa_roi', [.4, .58, .8, .86])
    assert len(roi) == 4 and 0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1
    box = tuple(int(value * (width if i % 2 == 0 else height)) for i, value in enumerate(roi))
    carrier, carrier2 = (yy+top)/36 + xx/135, (yy+top)/22 - xx/215
    sin0, cos0 = np.sin(carrier), np.cos(carrier2)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.stage.mp4', delete=False)
    stage = Path(temp.name)
    temp.close()
    qa = Image.new('RGB', (1200, 570), '#f7f1e4')
    changes, previous = [], None
    process = None
    try:
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen([
                'ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', f'{width}x{height}', '-r', str(FPS), '-i', '-', '-an',
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '12',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(stage)
            ], stdin=subprocess.PIPE, stderr=errors)
            for i in range(FRAMES):
                phase = 2 * math.pi * i / FRAMES
                if direction is not None:
                    # Constant downstream movement. The still matches the video at 1.5s.
                    # Live Photo playback needs continuous motion, not forced rewind/loop.
                    distance = (i/FPS-1.5) / 3 * travel
                    offset = mask * distance
                    if edge_distance is not None:
                        limit = .8 * edge_distance
                        offset = np.clip(offset, -limit, limit)
                    dx = -direction[0] * offset
                    dy = -direction[1] * offset
                else:
                    dx = mask * flow_x * (np.sin(carrier-phase) - sin0)
                    dy = mask * flow_y * (np.cos(carrier2-phase) - cos0)
                for fm, ax, ay in fields:
                    dx += fm * ax * math.sin(phase)
                    dy += fm * ay * math.sin(phase)
                sampled = np.stack([
                    map_coordinates(sub[:, :, channel], [yy+dy, xx+dx], order=1, mode='reflect')
                    for channel in range(3)
                ], axis=-1)
                if light_mask is not None:
                    sampled *= 1 + light_amplitude * (1-math.cos(phase))/2 * light_mask[:, :, None]
                tile = np.uint8(np.clip(sampled, 0, 255))
                # Restore exact source pixels beyond the authorized support.
                # Soft fields and float interpolation are not a protection contract.
                tile[~allowed] = original_tile[~allowed]
                if (~allowed).any():
                    difference = np.abs(tile[~allowed].astype(np.int16) - original_tile[~allowed])
                    protected_max_difference = max(protected_max_difference, int(difference.max()))
                    assert protected_max_difference == 0, 'Protected pixels changed before encoding'
                if previous is not None:
                    changes.append(float(np.abs(tile.astype(np.int16)-previous.astype(np.int16)).mean()))
                previous = tile
                frame = im.copy()
                frame.paste(Image.fromarray(tile), (0, top))
                process.stdin.write(frame.tobytes())
                if i in (0, 18, 36, 54, 71):
                    col = (0, 18, 36, 54, 71).index(i)
                    qa.paste(frame.resize((240, 320)), (col*240, 20))
                    crop = frame.crop(box)
                    crop.thumbnail((236, 190))
                    qa.paste(crop, (col*240, 370))
                    ImageDraw.Draw(qa).text((col*240+8, 4), f'{i/FPS:.2f}s', fill='black')
                if i % 24 == 0:
                    print(f'Frames {i+1}/{FRAMES}', flush=True)
            process.stdin.close()
            code = process.wait()
            if code:
                errors.seek(0)
                raise RuntimeError(errors.read().decode(errors='replace')[-2000:])
        assert min(changes) > 0, 'Some consecutive frames are identical; adjust visible local motion'
        with stage.open('rb') as stream:
            os.fsync(stream.fileno())
        info = probe(stage)
        assert (info['width'], info['height']) == im.size
        shutil.copyfile(stage, destination)
        probe(destination)
        if args.qa:
            qa_path = Path(args.qa).resolve()
            assert qa_path not in (src_path, destination), 'QA must have a separate path'
            qa_path.parent.mkdir(parents=True, exist_ok=True)
            qa.save(qa_path)
        print(json.dumps({'video': str(destination), 'duration': 3, 'frames': FRAMES,
                          'fps': FPS, 'size': im.size,
                          'protected_raw_max_difference': protected_max_difference,
                          'motion_support_pixels': int(allowed.sum()),
                          'minimum_frame_change': min(changes)}, ensure_ascii=False))
    finally:
        if process and process.poll() is None:
            process.kill()
            process.wait()
        stage.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('video')
    parser.add_argument('--config', required=True)
    parser.add_argument('--qa', help='Internal contact-sheet path; do not deliver to user')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--allow-subtle', action='store_true', help='Only for explicit user requests for nearly-static motion')
    run(parser.parse_args())
