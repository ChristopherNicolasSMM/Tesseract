"""Sobe servidor descartável e Playwright no mesmo processo de execução."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def main():
    with tempfile.TemporaryDirectory(prefix='reports-browser-') as temporary, tempfile.TemporaryFile(mode='w+') as log:
        env = {**os.environ, 'REPORTS_TEST_URL': 'http://127.0.0.1:5068',
               'REPORTS_TEST_DB': str(Path(temporary) / 'browser.sqlite')}
        server = subprocess.Popen([sys.executable, '-c',
            "import runpy; runpy.run_path('tests/browser/reports_server.py', run_name='__main__')"],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError('Servidor de teste terminou antes de ficar pronto.')
                try:
                    with opener.open(env['REPORTS_TEST_URL'] + '/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(.1)
            else:
                raise TimeoutError('Servidor de teste não respondeu em 30 segundos.')
            subprocess.run(['node', 'tests/browser/reports_editor.cjs'], cwd=ROOT, env=env, check=True, timeout=180)
        except Exception:
            log.seek(0)
            # Diagnóstico curto; não inundar a saída com SQL do boot.
            print(log.read()[-8000:], file=sys.stderr)
            raise
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait(timeout=5)


if __name__ == '__main__':
    main()
