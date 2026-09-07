"""Stage public static assets only. Never publish scripts, private state or source excerpts."""
import shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
target=root/'_site'
if target.exists(): shutil.rmtree(target)
target.mkdir()
for item in root.iterdir():
    if item.name.startswith('.') or item.name in ('scripts','_site','README.md','THIRD_PARTY_NOTICES.md'): continue
    if item.is_symlink(): raise ValueError('Unexpected symlink')
    if item.is_dir(): shutil.copytree(item,target/item.name,ignore=shutil.ignore_patterns('__pycache__','data'))
    else: shutil.copy2(item,target/item.name)
(target/'.nojekyll').touch()
