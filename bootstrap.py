#!/usr/bin/env python3
"""Explicit local environment installer. Does not install system programs."""
from pathlib import Path
import shutil
import subprocess
import sys
import venv

root = Path(__file__).resolve().parent
if sys.version_info < (3,10):
    sys.exit('需要 Python 3.10 或更新版本。')
target = root/'.venv'
venv.EnvBuilder(with_pip=True).create(target)
python = target/('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
subprocess.run([str(python),'-m','pip','install','-r',str(root/'requirements.txt')],check=True)
missing = [name for name in ('ffmpeg','ffprobe') if not shutil.which(name)]
if missing:
    print('Python 依赖已安装；系统还缺少 '+', '.join(missing)+'。请按 README 安装并加入 PATH。')
    sys.exit(1)
print('安装完成。运行 '+str(python)+' quickstart.py doctor')
