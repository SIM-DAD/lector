import re
import docx
import markdown
from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    # Remove numeric citation brackets: [1], [1,2], [1-3]
    text = re.sub(r'\[\d+(?:[,\s\-]\d+)*\]', '', text)
    # Remove author-year citations in brackets: [Smith et al., 2020]
    text = re.sub(r'\[[A-Z][^\[\]]{1,60}\d{4}[^\[\]]*\]', '', text)
    # Remove lone superscript-style numbers that are footnote markers (e.g. word1 → word)
    # Only remove trailing digit clusters after word chars with no space
    text = re.sub(r'(?<=\w)(?<![0-9])(\d{1,2})(?=[\s,\.;])', '', text)
    # Collapse extra whitespace
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def parse_docx(path: str) -> list[str]:
    doc = docx.Document(path)
    paragraphs = []
    for para in doc.paragraphs:
        text = clean_text(para.text)
        # Skip headings, short labels, empty lines
        if text and len(text) > 20:
            paragraphs.append(text)
    return paragraphs


def parse_md(path: str) -> list[str]:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    html = markdown.markdown(content, extensions=['tables'])
    soup = BeautifulSoup(html, 'html.parser')
    paragraphs = []
    for elem in soup.find_all(['p', 'li']):
        text = clean_text(elem.get_text())
        if text and len(text) > 20:
            paragraphs.append(text)
    return paragraphs


def parse_file(path: str) -> list[str]:
    if path.endswith('.docx'):
        return parse_docx(path)
    elif path.endswith('.md'):
        return parse_md(path)
    else:
        raise ValueError(f"Unsupported file type: {path}")
