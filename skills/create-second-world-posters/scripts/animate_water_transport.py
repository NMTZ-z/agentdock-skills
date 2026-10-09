#!/usr/bin/env python3
"""The validated smooth masked water transport baseline, packaged without job paths."""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, map_coordinates
from animate_local import smooth, probe


def require(condition, message):
    if not condition:
        raise ValueError(message)


def render(args, work):
    image, video, config_path = map(lambda p: Path(p).resolve(), (args.image, args.video, args.config))
    require(image.is_file() and config_path.is_file(), 'Image or configuration not found')
    require(not video.exists() or args.overwrite, 'Output exists; pass overwrite only when authorized')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    im = Image.open(image).convert('RGB')
    w, h = im.size
    require(w*4 == h*3 and w%2 == 0 and h%2 == 0, 'Expected even 3:4 portrait dimensions')
    bounds = config.get('bounds', [0, 1])
    require(len(bounds)==2 and 0 <= bounds[0] < bounds[1] <= 1, 'Invalid normalized bounds')
    top, bottom = round(bounds[0]*h), round(bounds[1]*h)
    require(bottom-top >= 8 and w >= 8, 'Motion region too small')
    inputs = {image, config_path}
    def mask_file(key):
        p = Path(config[key])
        if not p.is_absolute(): p = config_path.parent/p
        require(p.resolve() not in {image, video, config_path}, 'Mask and job paths must be distinct')
        inputs.add(p.resolve())
        with Image.open(p) as m:
            require(m.size == im.size, 'Mask must match image size')
            return np.asarray(m.convert('L'),dtype=np.float32)[top:bottom]/255
    mask = mask_file('water_mask')
    if config.get('protect_mask'):
        mask[mask_file('protect_mask') > 0] = 0
    require(np.any(mask > 0), 'Empty water mask')
    require(video.suffix.lower()=='.mp4' and video not in {image, config_path}, 'Distinct MP4 output required')
    if args.report:
        require(Path(args.report).resolve() not in inputs | {video}, 'Report must not overwrite input or video')
    direction = config.get('direction', [0, 1])
    require(len(direction)==2 and all(math.isfinite(float(x)) for x in direction), 'Invalid normalized direction')
    direction_pixels = [direction[0]*w, direction[1]*h]
    require(np.linalg.norm(direction_pixels) > 0, 'Direction must be nonzero')
    travel = float(config.get('travel_pixels', 64))
    fade = float(config.get('edge_fade_pixels', 180))
    require(math.isfinite(travel) and travel > 0 and math.isfinite(fade) and fade > 0, 'Travel and fade must be positive finite pixels')
    require(travel*390/w >= 4, 'Motion too small for phone preview; choose a visible travel')
    source = np.asarray(im, dtype=np.float32)[top:bottom]
    original = np.asarray(im, dtype=np.uint8)[top:bottom]
    allowed = mask > 0
    edge = distance_transform_edt(np.pad(allowed, 1))[1:-1,1:-1]
    mask *= smooth(edge/fade)
    yy, xx = np.indices(mask.shape, dtype=np.float32)
    video.parent.mkdir(parents=True, exist_ok=True)
    stride = 4
    gy, gx = np.indices(mask[::stride,::stride].shape, dtype=np.float32)
    direction = np.asarray(direction_pixels, dtype=np.float32)
    direction /= np.linalg.norm(direction)
    travel = float(config.get("travel_pixels", 64))
    speed = mask[::stride,::stride]*travel/(3*stride)
    vx, vy = direction[0]*speed, direction[1]*speed

    def velocity(y, x):
        return (map_coordinates(vy, [y,x], order=1, mode='constant', cval=0),
                map_coordinates(vx, [y,x], order=1, mode='constant', cval=0))

    def advance(y, x, dt):
        ay, ax = velocity(y,x)
        by, bx = velocity(y+.5*dt*ay, x+.5*dt*ax)
        return y+dt*by, x+dt*bx

    # Inverse flow maps: the still is the exact midpoint reference at 1.5s.
    qy, qx = gy.copy(), gx.copy()
    for _ in range(36):
        qy, qx = advance(qy,qx,1/24)

    stage = work/'transport.stage.mp4'
    proc = subprocess.Popen([
        'ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24',
        '-s',f'{w}x{h}','-r','24','-i','-','-an','-c:v','libx264',
        '-preset','medium','-crf','12','-pix_fmt','yuv420p',
        '-movflags','+faststart',str(stage)
    ], stdin=subprocess.PIPE)
    report = {'frames':72,'duration':3,'travel_pixels':travel,
              'protected_raw_max_difference':0,'minimum_sampling_jacobian':1.0,
              'maximum_sampling_jacobian':1.0,'folded_pixels':0,
              'maximum_principal_stretch':1.0,'minimum_principal_stretch':1.0}
    last = None
    changes = []
    try:
        for i in range(72):
            if i == 36:
                # Reset the reference exactly; midpoint numerical error is subpixel.
                error = float(np.max(np.hypot(qy-gy,qx-gx))*stride)
                require(error < .02, f'Midpoint flow integration drift: {error}')
                report['midpoint_integration_error_pixels'] = error
                qy, qx = gy.copy(), gx.copy()
            jyy,jyx = np.gradient(qy)
            jxy,jxx = np.gradient(qx)
            determinant = jyy*jxx-jyx*jxy
            trace = jyy*jyy+jyx*jyx+jxy*jxy+jxx*jxx
            disc = np.sqrt(np.maximum(trace*trace-4*determinant*determinant,0))
            largest = np.sqrt(np.maximum((trace+disc)/2,0))
            smallest = np.sqrt(np.maximum((trace-disc)/2,0))
            report['minimum_sampling_jacobian'] = min(report['minimum_sampling_jacobian'],float(determinant.min()))
            report['maximum_sampling_jacobian'] = max(report['maximum_sampling_jacobian'],float(determinant.max()))
            report['maximum_principal_stretch'] = max(report['maximum_principal_stretch'],float(largest.max()))
            report['minimum_principal_stretch'] = min(report['minimum_principal_stretch'],float(smallest.min()))
            report['folded_pixels'] += int((determinant<=0).sum())
            require(determinant.min() > .55, 'Excess compression or a folded flow map')
            require(largest.max() < 1.5 and smallest.min() > .65, 'Excess stretch')
            # Interpolate displacement rather than absolute coordinates so the
            # sampling grid remains identity at image edges and all fixed points.
            dy = map_coordinates((qy-gy)*stride,[yy/stride,xx/stride],order=1,mode='nearest')
            dx = map_coordinates((qx-gx)*stride,[yy/stride,xx/stride],order=1,mode='nearest')
            dy[~allowed] = 0
            dx[~allowed] = 0
            # Conservatively reject any sample which could cross an occluder.
            inside = map_coordinates(allowed.astype(np.float32),[yy+dy,xx+dx],order=1,mode='constant',cval=0)
            unsafe = allowed & (inside<.999)
            require(np.max(np.hypot(dx[unsafe],dy[unsafe]),initial=0) < .15, 'Source sample crosses protected foreground')
            dx[unsafe] = 0
            dy[unsafe] = 0
            # Check the actual full-resolution mapping as well as the integrated grid.
            dyy,dyx = np.gradient(dy)
            dxy,dxx = np.gradient(dx)
            det_full = (1+dyy)*(1+dxx)-dyx*dxy
            require(det_full.min() > .55, 'Fold in the final sampling map')
            report['minimum_sampling_jacobian'] = min(report['minimum_sampling_jacobian'],float(det_full.min()))
            tile = np.stack([map_coordinates(source[:,:,c],[yy+dy,xx+dx],order=1,mode='nearest') for c in range(3)],axis=-1)
            tile = np.uint8(np.clip(np.rint(tile),0,255))
            tile[~allowed] = original[~allowed]
            require(np.array_equal(tile[~allowed],original[~allowed]), 'Protected pixels changed')
            if last is not None:
                changes.append(float(np.abs(tile.astype(np.int16)-last.astype(np.int16)).mean()))
            last = tile
            frame = im.copy()
            frame.paste(Image.fromarray(tile),(0,top))
            proc.stdin.write(frame.tobytes())
            if i % 24 == 0:
                print(f'Rendered {i+1}/72; minimum mapping area scale {det_full.min():.3f}',file=sys.stderr,flush=True)
            qy,qx = advance(qy,qx,-1/24)
        proc.stdin.close()
        require(proc.wait()==0, 'ffmpeg encoding failed')
        require(min(changes)>0, 'No visible source texture change')
        probe(stage)
        shutil.copyfile(stage, video)
        report['minimum_frame_rgb_change']=min(changes)
        if args.report:
            destination = Path(args.report).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(report,indent=2), encoding='utf-8')
        print(json.dumps(report),flush=True)
    finally:
        if proc.poll() is None:
            proc.kill();proc.wait()
        stage.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('video')
    parser.add_argument('--config', required=True)
    parser.add_argument('--report')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='water-transport-') as temporary:
        render(args, Path(temporary))


if __name__ == '__main__':
    main()
