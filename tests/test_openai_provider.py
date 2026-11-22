import json
from types import SimpleNamespace

import pytest

from video_localizer.media import Segment
from video_localizer.openai_provider import OpenAIProviders


def provider_with_response(response):
    provider = object.__new__(OpenAIProviders)
    def create(**kwargs):
        values = json.loads(kwargs['messages'][1]['content'])
        content = response(values)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(content)))])
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return provider


def test_translation_batches_preserve_timestamps():
    provider = provider_with_response(lambda values: {'translations': ['訳文' for _ in values]})
    segments = [Segment(i, i + .5, 'hello') for i in range(30)]
    translated = provider.translate(segments, 'ja')
    assert translated == [Segment(s.start, s.end, '訳文') for s in segments]


@pytest.mark.parametrize('response', [{}, {'translations': []}, {'translations': [None]}, {'translations': ['']}])
def test_translation_rejects_missing_or_empty_segments(response):
    provider = provider_with_response(lambda values: response)
    with pytest.raises(RuntimeError):
        provider.translate([Segment(0, 1, 'hello')], 'ja')


def test_key_required(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        OpenAIProviders()
