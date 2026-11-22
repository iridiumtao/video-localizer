"""Real providers, synthetic input: exercise ASR -> translation -> Japanese TTS.

Run after installing .[local] and extracting an Argos English-to-Japanese model.
The test fixture is deliberately distinct from the user-requested YouTube video.
"""
import argparse
from pathlib import Path

from video_localizer.media import duration, ffmpeg
from video_localizer.pipeline import process
from video_localizer.providers import Providers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--translation-model', type=Path, required=True)
    parser.add_argument('--model', default='base')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists():
        parser.error('Use a new output directory')
    root.mkdir(parents=True)
    speech = root / 'english.mp3'
    Providers(voice='en-US-JennyNeural').synthesize(
        'Welcome to this video translation test. '
        'Today we are testing automatic Japanese dubbing and subtitles. '
        'The new voice should follow the original video timeline.',
        'en', speech,
    )
    video = root / 'synthetic-test-fixture.mp4'
    total = duration(speech) + 1
    ffmpeg('-f', 'lavfi', '-i', f'testsrc2=s=960x540:r=25:d={total}',
           '-i', str(speech), '-c:v', 'libx264', '-c:a', 'aac',
           '-t', str(total), str(video))
    result = process(str(video), root / 'japanese', language='ja', mode='both',
                     model=args.model, translation_model=args.translation_model)
    print('Synthetic fixture, real providers:', result)


if __name__ == '__main__':
    main()
