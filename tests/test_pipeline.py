import json
import shutil
import wave
from pathlib import Path

import pytest

from video_localizer.media import Segment, acquire, duration, ffmpeg, normalize, run, subtitles, tempo_filters
from video_localizer.pipeline import process


class TestServices:
    __test__ = False

    def transcribe(self, audio):
        return [Segment(.5, 1.2, "Hello"), Segment(2, 2.8, "World")], "en"

    def translate(self, segments, target):
        return [Segment(s.start, s.end, text) for s, text in zip(segments, ["こんにちは", "世界"])]

    def synthesize(self, text, target, path):
        # A tone deliberately longer than the subtitle slot exercises time fitting.
        ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=1.5", str(path))


@pytest.fixture
def video(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg required")
    video = tmp_path / "source with spaces.mp4"
    ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=4", "-f", "lavfi", "-i", "sine=frequency=220:duration=4", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(video))
    return video


@pytest.mark.parametrize("mode,audio_language,has_subtitles", [("both", "jpn", True), ("dub", "jpn", False), ("subtitles", None, True)])
def test_real_media_pipeline(video, tmp_path, mode, audio_language, has_subtitles):
    output = tmp_path / mode
    result = process(str(video), output, mode=mode, providers=TestServices())
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(result)]))
    streams = probe["streams"]
    assert abs(duration(result) - 4) < .15
    assert sum(s["codec_type"] == "subtitle" for s in streams) == int(has_subtitles)
    if audio_language:
        audio = next(s for s in streams if s["codec_type"] == "audio")
        assert audio["tags"]["language"] == audio_language
        with wave.open(str(output / "dubbing.wav"), "rb") as wav:
            assert wav.getnframes() == 4 * 24000
            assert wav.readframes(12000) == b"\0\0" * 12000  # preserve initial silence
            assert any(wav.readframes(1000))
    if has_subtitles:
        assert "こんにちは" in (output / "subtitles.srt").read_text()
        extracted = run(["ffmpeg", "-v", "error", "-i", str(result), "-map", "0:s:0", "-f", "srt", "-"])
        assert "こんにちは" in extracted
        assert "世界" in extracted
    assert json.loads((output / "manifest.json").read_text())["status"] == "completed"


def test_clip_and_protect_outputs(video, tmp_path):
    output = tmp_path / "clip"
    result = process(str(video), output, max_seconds=1.5, providers=TestServices())
    assert abs(duration(result) - 1.5) < .15
    with pytest.raises(ValueError, match="不是空"):
        process(str(video), output, providers=TestServices())


def test_failure_manifest(video, tmp_path):
    class NoSpeech(TestServices):
        def transcribe(self, audio):
            return [], "en"
    output = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="未偵測"):
        process(str(video), output, providers=NoSpeech())
    assert json.loads((output / "manifest.json").read_text())["status"] == "failed"
    assert not (output / "localized.mp4").exists()


def test_whisper_can_decode_real_audio(video):
    # PyAV 19 removed metadata_errors, still used by faster-whisper 1.2.1.
    # Exercise the real decoder to catch incompatible dependency updates.
    from faster_whisper.audio import decode_audio
    samples = decode_audio(str(video), sampling_rate=16000)
    assert abs(len(samples) / 16000 - 4) < .15
    assert max(abs(samples)) > .01


def test_normalize_and_subtitles(tmp_path):
    segments = normalize([Segment(-1, 1, "a\n\nb"), Segment(.5, 3, "日文"), Segment(4, 5, "outside")], 2)
    assert segments == [Segment(0, 1, "a b"), Segment(1, 2, "日文")]
    subtitles(segments, tmp_path)
    assert "00:00:01,000 --> 00:00:02,000" in (tmp_path / "subtitles.srt").read_text()
    assert (tmp_path / "subtitles.vtt").read_text().startswith("WEBVTT\n")
    assert "atempo=2,atempo=2" in tempo_filters(8)


@pytest.mark.parametrize("source", ["http://youtube.com/watch?v=x", "https://youtube.com.evil.test/x", "https://example.com/x", "https://user@youtube.com/x"])
def test_reject_other_urls(source, tmp_path):
    with pytest.raises(ValueError):
        acquire(source, tmp_path)
