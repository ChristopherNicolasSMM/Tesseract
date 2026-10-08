"""Worker de impressão; nenhuma URL externa ou arquivo local é carregado."""
import sys


def blocked_fetcher(*args, **kwargs):
    raise ValueError('External resources are disabled')


def main():
    try:
        import resource
        memory = int(sys.argv[1]) * 1024 * 1024
        timeout = int(sys.argv[2])
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
    except ImportError:
        pass  # Windows: timeout do pai; limite de memória via infraestrutura posteriormente.
    from weasyprint import HTML
    html = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
    if len(html) > 2 * 1024 * 1024:
        return 1
    pdf = HTML(string=html.decode('utf-8'), url_fetcher=blocked_fetcher).write_pdf()
    if len(pdf) > 10 * 1024 * 1024:
        return 1
    sys.stdout.buffer.write(pdf)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
