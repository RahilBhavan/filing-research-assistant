"""Answer providers. Each returns {'text', 'latency_s', 'cost_usd', 'usage'}.

anthropic   Messages API via the official SDK and ANTHROPIC_API_KEY (default).
claude-cli  Claude Code CLI in headless mode. A backend adapter for machines
            with a Claude Code login but no API key; it is how the committed
            evaluation was run. Its cost is the CLI's list-price estimate.
ollama      Local model through Ollama's HTTP API (local fallback, needs a pull).
extractive  No model: returns the best-overlapping sentence of the top passage
            as a quote. Offline fallback so the server always answers or abstains.
"""
import json
import os
import re
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen
from .engine import tokens

DEFAULT_MODEL = 'claude-haiku-5-5'
# USD per million tokens, prompts up to 100K tokens (Anthropic list price, cached 2026-10-06).
PRICES = {'claude-haiku-5-5': (0.10, 0.50)}


class AnthropicProvider:
    name = 'anthropic'

    def __init__(self, model=DEFAULT_MODEL, client=None):
        self.model = model
        if client is None:
            if not os.environ.get('ANTHROPIC_API_KEY'):
                raise ValueError('Set ANTHROPIC_API_KEY to use the anthropic provider')
            import anthropic
            client = anthropic.Anthropic()
        self.client = client

    def complete(self, system, user):
        started = time.monotonic()
        # Haiku 5.5 thinks adaptively by default; low effort keeps this narrow
        # quoting task cheap. Sampling parameters are rejected on this model.
        message = self.client.messages.create(model=self.model, max_tokens=2048, system=system,
                                              messages=[{'role': 'user', 'content': user}], output_config={'effort': 'low'})
        latency = time.monotonic() - started
        if message.stop_reason == 'refusal':
            text = '{"status": "abstained", "answer": "", "citations": []}'
        else:
            text = ''.join(block.text for block in message.content if block.type == 'text')
        usage = dict(input_tokens=message.usage.input_tokens, output_tokens=message.usage.output_tokens)
        price = PRICES.get(self.model)
        cost = (usage['input_tokens']*price[0] + usage['output_tokens']*price[1])/1e6 if price else None
        return dict(text=text, latency_s=latency, cost_usd=cost, usage=usage)


class ClaudeCliProvider:
    """`claude -p` with tools, MCP, settings and session persistence switched off."""
    name = 'claude-cli'

    def __init__(self, model='haiku', binary='claude', timeout=180, runner=subprocess.run):
        self.model, self.binary, self.timeout, self.runner = model, binary, timeout, runner
        self.workdir = tempfile.mkdtemp(prefix='filing-cli-')

    def complete(self, system, user):
        command = [self.binary, '-p', '--model', self.model, '--output-format', 'json', '--tools', '',
                   '--system-prompt', system, '--strict-mcp-config', '--setting-sources', '', '--no-session-persistence']
        started = time.monotonic()
        done = self.runner(command, input=user, capture_output=True, text=True, timeout=self.timeout, cwd=self.workdir)
        latency = time.monotonic() - started
        if done.returncode != 0:
            raise RuntimeError('claude CLI failed: ' + (done.stderr or done.stdout)[-300:])
        result = json.loads(done.stdout)
        if result.get('is_error'):
            raise RuntimeError('claude CLI error: ' + str(result.get('result'))[:300])
        models = result.get('modelUsage') or {}
        usage = dict(result.get('usage') or {}, models=sorted(models), api_duration_ms=result.get('duration_api_ms'))
        return dict(text=result.get('result', ''), latency_s=latency, cost_usd=result.get('total_cost_usd'), usage=usage)


class OllamaProvider:
    name = 'ollama'

    def __init__(self, model='qwen2.5:0.5b', host='http://127.0.0.1:11434', opener=urlopen):
        self.model, self.host, self.opener = model, host.rstrip('/'), opener

    def complete(self, system, user):
        body = json.dumps(dict(model=self.model, stream=False, format='json', options=dict(temperature=0),
                               messages=[dict(role='system', content=system), dict(role='user', content=user)])).encode()
        started = time.monotonic()
        with self.opener(Request(self.host + '/api/chat', data=body, headers={'Content-Type': 'application/json'}), timeout=300) as response:
            payload = json.loads(response.read())
        usage = dict(input_tokens=payload.get('prompt_eval_count'), output_tokens=payload.get('eval_count'))
        return dict(text=payload['message']['content'], latency_s=time.monotonic() - started, cost_usd=0.0, usage=usage)


class ExtractiveProvider:
    """Deterministic, model-free: quote the sentence with the most question terms."""
    name = 'extractive'
    min_overlap = 0.5

    def complete(self, system, user):
        started = time.monotonic()
        question = re.search(r'^Question: (.*)$', user, re.M).group(1)
        terms = set(tokens(question))
        best = (0.0, None, None)
        for pid, text in re.findall(r'\[passage_id: ([^\]]+)\] \([^\n]*\)\n(.*?)(?=\n\n\[passage_id: |\Z)', user, re.S):
            for sentence in re.split(r'(?<=[.!?])\s+', text.strip()):
                overlap = len(terms & set(tokens(sentence)))/max(1, len(terms))
                if overlap > best[0]:
                    best = (overlap, pid, sentence)
        if best[0] < self.min_overlap:
            out = dict(status='abstained', answer='', citations=[])
        else:
            out = dict(status='answered', answer=best[2], citations=[dict(passage_id=best[1], quote=best[2])])
        return dict(text=json.dumps(out), latency_s=time.monotonic() - started, cost_usd=0.0, usage={})


def make_provider(name=None, model=None):
    name = name or ('anthropic' if os.environ.get('ANTHROPIC_API_KEY') else 'extractive')
    if name == 'anthropic':
        return AnthropicProvider(model or DEFAULT_MODEL)
    if name == 'claude-cli':
        return ClaudeCliProvider(model or 'haiku')
    if name == 'ollama':
        return OllamaProvider(model or 'qwen2.5:0.5b')
    if name == 'extractive':
        return ExtractiveProvider()
    raise ValueError('Unknown provider')
