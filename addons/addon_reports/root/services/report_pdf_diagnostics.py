"""Diagnóstico local do worker real, sem Flask/DB ou dados de negócio.

Executar no mesmo venv e ambiente que inicia o Tesseract. O stderr detalhado
é exibido somente neste comando, com HTML fictício controlado.
"""
from pathlib import Path
import os
import platform
import subprocess
import sys

WORKER = 'addons.addon_reports.root.services.report_pdf_worker'
ROOT = Path(__file__).resolve().parents[4]


def main():
    print('Python:', sys.executable)
    print('Platform:', platform.platform())
    print('WEASYPRINT_DLL_DIRECTORIES:', os.environ.get('WEASYPRINT_DLL_DIRECTORIES', '(not set)'))
    print('Linux memory limit: 1024 MiB; worker timeout: 30 seconds')
    commands = [([sys.executable, '-m', 'weasyprint', '--info'], None),
                ([sys.executable, '-m', WORKER, '1024', '30'],
                 '<!doctype html><meta charset="utf-8"><h1>Acentuação — relatório de teste</h1>'.encode('utf-8'))]
    success = True
    for command, sample in commands:
        print('\nCommand:', ' '.join(command))
        try:
            result = subprocess.run(command, input=sample, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=35, cwd=ROOT)
        except (OSError, subprocess.TimeoutExpired) as error:
            print('Failed:', type(error).__name__, str(error)); success = False; continue
        print('Exit:', result.returncode)
        if sample is None:
            print(result.stdout.decode('utf-8', errors='replace')[:8000])
            success = success and result.returncode == 0
        else:
            valid = result.returncode == 0 and result.stdout.startswith(b'%PDF-') and len(result.stdout) <= 10 * 1024 * 1024
            print('PDF signature:', result.stdout[:5], 'bytes:', len(result.stdout), 'valid:', valid)
            success = success and valid
        if result.stderr:
            print('Diagnostic stderr (controlled sample only):\n' + result.stderr.decode('utf-8', errors='replace')[:12000])
    return 0 if success else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='backslashreplace')
    raise SystemExit(main())
