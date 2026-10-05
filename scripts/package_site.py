"""Stage public static assets only. Never publish scripts, private state or source excerpts."""
import json, os, shutil, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
target=root/'_site'
ANALYTICS=os.environ.get('ANALYTICS_SNIPPET','').strip()
def inject_analytics(html_text):
    """Inject the owner-configured analytics snippet before </head> on every page."""
    if not ANALYTICS or '</head>' not in html_text: return html_text
    return html_text.replace('</head>',ANALYTICS+'\n</head>',1)
if target.exists(): shutil.rmtree(target)
target.mkdir()
for item in root.iterdir():
    if item.name.startswith('.') or item.name in ('scripts','_site','README.md','THIRD_PARTY_NOTICES.md'): continue
    if item.is_symlink(): raise ValueError('Unexpected symlink')
    if item.is_dir():
        shutil.copytree(item,target/item.name,ignore=shutil.ignore_patterns('__pycache__','data'))
    else:
        shutil.copy2(item,target/item.name)
for html_file in target.rglob('*.html'):
    html_file.write_text(inject_analytics(html_file.read_text(encoding='utf-8')),encoding='utf-8')
(target/'.nojekyll').touch()
if os.environ.get('GITHUB_RUN_ID'):
    # Public deployment evidence identifies the exact committed source snapshot.
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    (target/'daily'/'deployment.json').write_text(json.dumps({
        'source_commit':revision,
        'run_url':'https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],
    },indent=2)+'\n',encoding='utf-8')
print('Analytics snippet injected' if ANALYTICS else 'No ANALYTICS_SNIPPET set; pages left untouched')
