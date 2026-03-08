import re
import docx
from pathlib import Path


def _clean_citations(text: str) -> str:
    # Remove numeric citation brackets: [1], [1,2], [1-3]
    text = re.sub(r'\[\d+(?:[,\s\-]\d+)*\]', '', text)
    # Remove author-year citations in brackets: [Smith et al., 2020]
    text = re.sub(r'\[[A-Z][^\[\]]{1,60}\d{4}[^\[\]]*\]', '', text)
    # Remove lone superscript-style footnote markers (e.g. word1 → word)
    text = re.sub(r'(?<=\w)(?<![0-9])(\d{1,2})(?=[\s,\.;])', '', text)
    return text


def _runs_to_md(para) -> str:
    """Convert a paragraph's runs to a Markdown inline string."""
    parts = []
    for run in para.runs:
        text = run.text
        if not text:
            continue
        if run.bold and run.italic:
            text = f"***{text}***"
        elif run.bold:
            text = f"**{text}**"
        elif run.italic:
            text = f"*{text}*"
        parts.append(text)
    result = "".join(parts)
    result = _clean_citations(result)
    result = re.sub(r'  +', ' ', result).strip()
    return result


def parse_docx(path: str) -> str:
    doc = docx.Document(path)
    lines = []
    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ""

        if style_name.startswith("Heading"):
            try:
                level = int(style_name.split()[-1])
            except (ValueError, IndexError):
                level = 1
            level = min(max(level, 1), 6)
            text = _clean_citations(para.text).strip()
            if text:
                lines.append("#" * level + " " + text)
        else:
            text = _runs_to_md(para)
            if text:
                lines.append(text)

    return "\n\n".join(lines)


def parse_md(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def parse_file(path: str) -> str:
    if path.endswith('.docx'):
        return parse_docx(path)
    elif path.endswith('.md'):
        return parse_md(path)
    else:
        raise ValueError(f"Unsupported file type: {path}")
