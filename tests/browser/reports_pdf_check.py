"""Conferência dos PDFs do Chromium; pypdf é dependência somente de desenvolvimento."""
from pathlib import Path
import re
import sys
import unicodedata
from pypdf import PdfReader


def check(path, width_mm, height_mm):
    reader = PdfReader(path)
    assert len(reader.pages) >= 3
    texts = []
    for index, page in enumerate(reader.pages, 1):
        assert abs(float(page.mediabox.width) - width_mm*72/25.4) < 1
        assert abs(float(page.mediabox.height) - height_mm*72/25.4) < 1
        text = unicodedata.normalize('NFKC', page.extract_text())
        assert f'Página {index} de {len(reader.pages)}' in text
        if 'ITEM_' in text:
            assert 'Descrição' in text and 'Valor' in text
        texts.append(text)
    markers = re.findall(r'ITEM_\d{3}', '\n'.join(texts))
    assert markers == [f'ITEM_{index:03}' for index in range(1, 101)]
    assert 'Fechamento final' in texts[-1] and 'ITEM_' not in texts[-1]
    assert 'Relatório de paginação' in texts[0]
    assert 'Coluna esquerda' in texts[0] and 'Coluna direita' in texts[0]
    resources = reader.pages[0]['/Resources'].get('/XObject', {})
    assert any(value.get_object().get('/Subtype') == '/Image' for value in resources.values())
    print(f'{path.name}: {len(reader.pages)} páginas, papel correto, 100 linhas preservadas, cabeçalhos, imagem e numeração aprovados')


if __name__ == '__main__':
    folder = Path(sys.argv[1])
    check(folder/'reports-pagination-landscape.pdf', 210, 148)
    check(folder/'reports-pagination-portrait.pdf', 210, 297)
    assert len(PdfReader(folder/'reports-browser-print.pdf').pages) == 2
