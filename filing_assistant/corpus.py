"""Parse visible narrative blocks while retaining document provenance."""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

SECTIONS = {'business', 'mda', 'risks'}
BLOCKS = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'section', 'article'}
VOID = {'br', 'hr', 'img', 'meta', 'link', 'input', 'wbr', 'source', 'area', 'base', 'embed', 'param', 'col'}
IGNORE = {'script', 'style', 'head', 'nav', 'table', 'ix:hidden', 'xbrli:context', 'xbrli:unit'}


def section_name(text):
    text = text.lower().replace('\u2019', "'").strip()
    text = re.sub(r'^item\s+\d+[a-z]?[. :–—-]*', '', text).strip()
    if text in {'risk factors', 'summary of risk factors'}:
        return 'risks'
    if re.match(r"^management(?:'?s)? discussion and analysis", text) and len(text) < 120:
        return 'mda'
    if text.strip() == 'business' or re.match(r'^item\s+1[. :]+business', text):
        return 'business'
    return None


class NarrativeParser(HTMLParser):
    """A small visible-block parser, not a complete SEC HTML layout engine.

    Tables are deliberately excluded so headers, units and cells cannot be
    mistaken for complete narrative evidence. Character offsets refer to the
    normalized narrative text, not the original HTML byte stream.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.buffer = []
        self.kind = 'text'
        self.anchor = None
        self.nearest_anchor = None
        self.section = None
        self.blocks = []
        self.omitted_tables = 0

    def flush(self):
        text = re.sub(r'\s+', ' ', ''.join(self.buffer)).strip()
        self.buffer = []
        if not text:
            return
        heading = self.kind in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
        identified = section_name(text) if len(text) < 180 else None
        item_heading = bool(re.match(r'^Item\s+\d+[A-Z]?[. :]', text, re.I)) and len(text) < 180
        if heading or identified or item_heading:
            if identified:
                self.section = identified
            elif self.kind in {'h1', 'h2'} or item_heading:
                self.section = None
        elif self.section and (len(text.split()) >= 6 or text.lower() == 'none.'):
            if not re.search(r'\|\s*20\d\d\s+Form\s+10-[KQ]\s*\|', text):
                self.blocks.append({'section': self.section, 'text': text, 'anchor': self.anchor or self.nearest_anchor})
        self.anchor = None
        self.kind = 'text'

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        parent_hidden = bool(self.stack and self.stack[-1][1])
        style = re.sub(r'\s+', '', attrs.get('style', '').lower())
        own_hidden = tag in IGNORE or 'hidden' in attrs or attrs.get('aria-hidden') == 'true' or 'display:none' in style or 'visibility:hidden' in style
        hidden = parent_hidden or own_hidden
        if not parent_hidden and (tag in BLOCKS or own_hidden):
            self.flush()
        if tag == 'table' and not parent_hidden:
            self.omitted_tables += 1
        if not hidden and tag in BLOCKS:
            self.kind, self.anchor = tag, attrs.get('id')
            if self.anchor:
                self.nearest_anchor = self.anchor
        if not hidden and tag == 'a' and (attrs.get('id') or attrs.get('name')):
            self.nearest_anchor = attrs.get('id') or attrs.get('name')
        if tag not in VOID:
            self.stack.append((tag, hidden))
        elif tag == 'br' and not hidden:
            self.buffer.append(' ')

    def handle_endtag(self, tag):
        hidden = bool(self.stack and self.stack[-1][1])
        if not hidden and tag in BLOCKS:
            self.flush()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if not self.stack or not self.stack[-1][1]:
            self.buffer.append(data)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)


def contained_path(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if root not in target.parents:
        raise ValueError('Corpus paths must stay inside the project directory')
    return target


def load_manifest(root):
    manifest = json.loads((Path(root) / 'data/manifest.json').read_text())
    if manifest.get('schema_version') != 1 or not manifest.get('documents'):
        raise ValueError('Unsupported or empty manifest')
    required = {'id', 'company', 'ticker', 'cik', 'accession', 'form', 'report_period', 'filing_date', 'source_kind', 'source_url', 'local_path', 'sha256', 'retrieved_at'}
    seen = set()
    for doc in manifest['documents']:
        if not required.issubset(doc):
            raise ValueError('Missing provenance fields')
        if doc['accession'] in seen:
            raise ValueError('Duplicate accession')
        seen.add(doc['accession'])
        if doc['source_kind'] not in {'synthetic_fixture', 'sec'}:
            raise ValueError('Unknown source kind')
        if doc['source_kind'] == 'synthetic_fixture' and (doc['cik'] is not None or doc['source_url'] is not None):
            raise ValueError('Synthetic fixtures cannot claim SEC identifiers or URLs')
        if doc['source_kind'] == 'sec' and (not doc['cik'] or not doc['source_url'] or not doc['retrieved_at']):
            raise ValueError('SEC sources require a CIK, URL and retrieval timestamp')
    return manifest


def build_index(root):
    root = Path(root)
    manifest = load_manifest(root)
    passages, diagnostics = [], []
    seen_ids = set()
    for doc in manifest['documents']:
        raw = contained_path(root, doc['local_path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != doc['sha256']:
            raise ValueError('Source hash mismatch: ' + doc['id'])
        parser = NarrativeParser()
        parser.feed(raw.decode('utf-8-sig'))
        parser.close()
        parser.flush()
        offset = 0
        for ordinal, block in enumerate(parser.blocks):
            # Bound large paragraphs without discarding text or inventing overlap.
            text = block['text']
            slices = []
            start = 0
            while start < len(text):
                end = min(start + 1800, len(text))
                if end < len(text):
                    boundary = text.rfind(' ', start, end)
                    if boundary > start:
                        end = boundary
                slices.append((start, end))
                start = end
                while start < len(text) and text[start] == ' ':
                    start += 1
            for part, (start, end) in enumerate(slices):
                pid = block['anchor'] or '{}-p{:04d}'.format(doc['id'], ordinal)
                if len(slices) > 1:
                    pid += '-part' + str(part)
                if pid in seen_ids:
                    pid = doc['id'] + '-' + str(ordinal) + '-' + str(part)
                if pid in seen_ids:
                    raise ValueError('Duplicate passage ID')
                seen_ids.add(pid)
                passages.append(dict(doc, passage_id=pid, section=block['section'], text=text[start:end], start_char=offset + start, end_char=offset + end, anchor=block['anchor']))
            offset += len(text) + 1
        diagnostics.append({'document_id': doc['id'], 'narrative_blocks': len(parser.blocks), 'omitted_tables': parser.omitted_tables})
        if not parser.blocks:
            raise ValueError('No supported narrative sections found: ' + doc['id'])
    index = {'schema_version': 1, 'manifest_sha256': hashlib.sha256((root/'data/manifest.json').read_bytes()).hexdigest(), 'notice': manifest['notice'], 'passages': passages, 'diagnostics': diagnostics}
    return index


def write_index(root):
    index = build_index(root)
    path = Path(root)/'data/index.json'
    path.write_text(json.dumps(index, indent=2) + '\n')
    return index
