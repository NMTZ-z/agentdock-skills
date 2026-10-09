import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT/'skills/create-second-world-posters'


def invoke(data):
    result = subprocess.run([sys.executable, '-B', 'run.py'], cwd=SKILL,
                            input=json.dumps(data), capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout)


class ReleaseTests(unittest.TestCase):
    def test_input_and_readonly_status(self):
        snapshot = {str(p.relative_to(SKILL)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in SKILL.rglob('*') if p.is_file()}
        code, result = invoke({'skill_action': 'status'})
        self.assertEqual(code, 0)
        self.assertTrue(result['ready'])
        after = {str(p.relative_to(SKILL)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in SKILL.rglob('*') if p.is_file()}
        self.assertEqual(snapshot, after)
        for data in [[], {'skill_action': 'unknown'}, {'skill_action': 'animate'}]:
            code, result = invoke(data)
            self.assertNotEqual(code, 0)
            self.assertEqual(result['code'], 'INVALID_INPUT')

    def test_actual_masked_video_and_rejections(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            w, h = 480, 640
            yy, xx = np.indices((h, w))
            texture = 90+50*np.sin(xx/5 + yy/9)
            rgb = np.stack([texture, texture+20, texture+50], axis=-1).astype('uint8')
            # A fixed foreground island inside the water domain.
            rgb[250:380, 200:230] = [40, 90, 30]
            image = job/'poster.png'
            Image.fromarray(rgb).save(image)
            mask = np.zeros((h, w), 'uint8')
            mask[160:520, 50:430] = 255
            mask[250:380, 200:230] = 0
            Image.fromarray(mask).save(job/'mask.png')
            config = job/'motion.json'
            config.write_text(json.dumps({'bounds':[0.2,0.9], 'water_mask':'mask.png',
                                          'direction':[0.2,0.8], 'travel_pixels':16,
                                          'edge_fade_pixels':90}))
            video = job/'poster_3s.mp4'
            report = job/'report.json'
            request = {'skill_action':'animate', 'image':str(image), 'video':str(video),
                       'config':str(config), 'report':str(report)}
            code, result = invoke(request)
            self.assertEqual(code, 0, result)
            metrics = json.loads(report.read_text())
            self.assertEqual(metrics['protected_raw_max_difference'], 0)
            self.assertEqual(metrics['folded_pixels'], 0)
            self.assertGreater(metrics['minimum_sampling_jacobian'], .55)
            code, result = invoke({'skill_action':'check_pair','image':str(image),'video':str(video)})
            self.assertEqual(code, 0, result)
            before = hashlib.sha256(video.read_bytes()).hexdigest()
            code, result = invoke(request)
            self.assertNotEqual(code, 0)
            self.assertEqual(before, hashlib.sha256(video.read_bytes()).hexdigest())
            code, result = invoke({'skill_action':'audit_motion','video':str(video),
                                   'roi':[.12,.25,.88,.8]})
            self.assertEqual(code, 0, result)
            self.assertFalse(result['result']['suspect_nearly_static'])
            config.write_text(json.dumps({'water_mask':'mask.png', 'direction':[0,0]}))
            request['video'] = str(job/'invalid.mp4')
            code, result = invoke(request)
            self.assertNotEqual(code, 0)
            self.assertFalse((job/'invalid.mp4').exists())
            self.assertTrue(image.exists())


if __name__ == '__main__':
    unittest.main()
