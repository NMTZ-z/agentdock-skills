import base64
from io import BytesIO
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import unittest
import subprocess
import sys
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('poster_tools',ROOT/'skills/create-second-world-posters/scripts/poster_tools.py')
poster=importlib.util.module_from_spec(spec);spec.loader.exec_module(poster)

class PosterTests(unittest.TestCase):
    def test_stale_selection_refused_before_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);Image.new('RGB',(96,128),'blue').save(p/'poster.png')
            (p/'motion.json').write_text(json.dumps({'image_sha256':'0'*64}))
            data={'skill_action':'animate','image':str(p/'poster.png'),'config':str(p/'motion.json'),'video':str(p/'video.mp4')}
            result=subprocess.run([sys.executable,'-B',str(ROOT/'skills/create-second-world-posters/run.py')],input=json.dumps(data),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertEqual(json.loads(result.stdout)['code'],'STALE_MOTION_SELECTION');self.assertFalse((p/'video.mp4').exists())

    def test_crop_and_no_key_no_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);Image.new('RGB',(1200,900),'blue').save(p/'source.png')
            data={'image':str(p/'source.png'),'location':'湖','output_dir':str(p/'job')}
            with patch.dict(os.environ,{},clear=True):
                with self.assertRaises(poster.PosterError) as ctx:poster.create_poster(data)
                self.assertEqual(ctx.exception.code,'MISSING_API_KEY')
            self.assertFalse((p/'job').exists())
            self.assertTrue(Path(poster.preview_poster(data)['preview']).exists())
            with self.assertRaises(poster.PosterError):poster.prepare_job({**data,'max_crop':float('nan'),'overwrite':True})
            with self.assertRaises(poster.PosterError):poster.prepare_canvas(p/'source.png',width=1152.5)
            (p/'collision').mkdir();(p/'collision/poster.png').symlink_to(p/'source.png')
            with patch.dict(os.environ,{'SENSENOVA_API_KEY':'test-key'}):
                with self.assertRaises(poster.PosterError):poster.create_poster({**data,'output_dir':str(p/'collision'),'overwrite':True})

    def test_http_preservation_and_private_errors(self):
        state={'mode':'image','requests':0}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                state['requests']+=1
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if state['mode']=='error':
                    self.send_response(401);self.end_headers();self.wfile.write(b'private-test-key');return
                if state['mode']=='redirect':
                    self.send_response(302);self.send_header('Location','http://127.0.0.1:1/stolen');self.end_headers();return
                size=tuple(map(int,payload['size'].split('x')))
                if state['mode']=='mismatch':size=(96,128)
                stream=BytesIO();Image.new('RGB',size,'red').save(stream,format='PNG')
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'data':[{'b64_json':base64.b64encode(stream.getvalue()).decode()}]}).encode())
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SENSENOVA_API_KEY':'private-test-key','SENSENOVA_BASE_URL':f'http://127.0.0.1:{server.server_port}/v1'}):
                p=Path(tmp);Image.new('RGB',(1200,900),'blue').save(p/'source.png')
                data={'image':str(p/'source.png'),'location':'湖','output_dir':str(p/'job'),'width':768}
                result=poster.create_poster(data);self.assertEqual(result['report']['preserved_photo_max_difference'],0)
                with Image.open(p/'job/poster.png') as im:
                    self.assertEqual(im.getpixel((0,0)),(0,0,255));self.assertEqual(im.getpixel((0,1023)),(255,0,0))
                for mode,code in [('error','SERVICE_HTTP_ERROR'),('redirect','SERVICE_HTTP_ERROR'),('mismatch','IMAGE_SIZE_MISMATCH')]:
                    state['mode']=mode
                    with self.assertRaises(poster.PosterError) as ctx:poster.create_poster({**data,'output_dir':str(p/mode)})
                    self.assertEqual(ctx.exception.code,code);self.assertNotIn('private-test-key',str(ctx.exception));self.assertFalse((p/mode).exists())
                self.assertEqual(state['requests'],4)
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
