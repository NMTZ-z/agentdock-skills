#!/usr/bin/env python3
"""Human CLI. Uses the same Skill entry point; no GPT dependency."""
import argparse
import json
from pathlib import Path
import subprocess
import shutil
import sys

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT/'skills/create-second-world-posters/run.py'


def invoke(data):
    worker = subprocess.run([sys.executable, '-B', str(ENTRY)], input=json.dumps(data),
                            capture_output=True, text=True)
    try:
        result = json.loads(worker.stdout)
    except ValueError:
        raise RuntimeError('入口无法运行，请先安装依赖并执行 doctor。') from None
    if not result.get('ok'):
        raise RuntimeError(f"{result.get('code')}: {result.get('message')}")
    return result


def main():
    parser = argparse.ArgumentParser(description='照片 → 第二世界海报 → 三秒水纹视频')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='检查依赖和图片接口配置，不上传照片')
    for name in ('prepare', 'poster'):
        p = commands.add_parser(name, help='本地裁切预览' if name == 'prepare' else '上传预排版照片生成海报')
        p.add_argument('image'); p.add_argument('--location', required=True)
        p.add_argument('--caption'); p.add_argument('--idea', default='')
        p.add_argument('--out', required=True); p.add_argument('--width', type=int, default=1152)
        p.add_argument('--photo-share', type=float, default=.58)
        p.add_argument('--crop-anchor', nargs=2, type=float, default=[.5,1])
        p.add_argument('--max-crop', type=float, default=.2)
        p.add_argument('--overwrite', action='store_true')
    for name in ('select', 'animate'):
        p = commands.add_parser(name)
        p.add_argument('image'); p.add_argument('--out', required=True)
        p.add_argument('--overwrite', action='store_true')
    p = commands.add_parser('demo', help='无需图片 API，用已公开示例导出视频')
    p.add_argument('--out', required=True); p.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'doctor':
            result = invoke({'skill_action':'status'})
        elif args.command in ('prepare','poster'):
            data = vars(args).copy(); data['skill_action'] = data.pop('command')
            data['output_dir'] = data.pop('out')
            result = invoke(data)
        elif args.command == 'select':
            result = invoke({'skill_action':'select_motion','image':args.image,
                             'output_dir':args.out,'overwrite':args.overwrite})
        else:
            job = Path(args.out).resolve()
            image = ROOT/'examples/sayram/poster.png' if args.command == 'demo' else Path(args.image).resolve()
            config = ROOT/'examples/sayram/motion.json' if args.command == 'demo' else job/'motion.json'
            video = job/'poster_3s.mp4'
            poster_copy = job/'poster.png'
            if args.command == 'demo' and (poster_copy.is_symlink() or poster_copy.resolve()==image.resolve()):
                raise RuntimeError('示例输出需使用独立任务目录。')
            if args.command == 'demo' and poster_copy.exists() and not args.overwrite:
                raise RuntimeError('任务图片已存在；需要明确 --overwrite 才能覆盖。')
            from PIL import Image
            settings=json.loads(config.read_text(encoding='utf-8'))
            mask_path=Path(settings['water_mask'])
            if not mask_path.is_absolute():mask_path=config.parent/mask_path
            with Image.open(mask_path) as opened:
                mask=opened.convert('L');box=mask.getbbox()
                if not box:raise RuntimeError('水面遮罩为空，请重新选择。')
                roi=[box[0]/mask.width,box[1]/mask.height,box[2]/mask.width,box[3]/mask.height]
            motion = invoke({'skill_action':'animate','image':str(image),'video':str(video),
                             'config':str(config),'report':str(job/'transport_report.json'),
                             'overwrite':args.overwrite})
            pair = invoke({'skill_action':'check_pair','image':str(image),'video':str(video)})
            audit = invoke({'skill_action':'audit_motion','video':str(video),
                            'roi':roi,'report':str(job/'audit_report.json')})
            if audit['result'].get('suspect_nearly_static'):
                raise RuntimeError(f'已导出 {video}，但所选水面疑似静止；请检查选区、纹理和实际播放效果。')
            if args.command == 'demo':
                shutil.copyfile(image,poster_copy)
            result = {'ok':True,'video':str(video),'motion':motion['result'],
                      'format':pair['result'],'audit':audit['result'],
                      'next':'查看三秒全片，确认水流可见、岸线与文字固定；数值检查不代替目视验收。'}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print(str(error),file=sys.stderr); return 1


if __name__=='__main__':
    sys.exit(main())
