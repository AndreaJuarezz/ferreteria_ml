import unicodedata

from django import template

register = template.Library()


@register.filter(name='ascii_text')
def ascii_text(value):
    if value is None:
        return ''
    text = str(value)
    for encoding in ('cp850', 'cp437', 'cp1252', 'latin1'):
        try:
            repaired = text.encode(encoding).decode('utf-8')
            if repaired != text:
                text = repaired
                break
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    normalized = unicodedata.normalize('NFKD', text)
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
    return ascii_text
