#!/usr/bin/env python3
import argparse
import shlex
import subprocess
import tempfile
from pathlib import Path


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def run_capture(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def ensure_ffmpeg_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        try:
            run([tool, "-version"])
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise RuntimeError(f"{tool} is required but not available in PATH") from exc


def probe_duration_seconds(video_path: Path) -> float:
    output = run_capture(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
    )
    return float(output)


def build_concat_file(clips: list[Path], concat_file: Path) -> None:
    lines = [f"file {shlex.quote(str(path.resolve()))}" for path in clips]
    concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def transition_times(clips: list[Path]) -> list[float]:
    times: list[float] = []
    cumulative = 0.0
    for clip in clips[:-1]:
        cumulative += probe_duration_seconds(clip)
        times.append(cumulative)
    return times


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Combine multiple short clips into a single edited vertical video."
    )
    parser.add_argument("clips", nargs="+", help="Input short clip files in playback order")
    parser.add_argument("-o", "--output", default="final_video.mp4", help="Output video path")
    parser.add_argument(
        "--music", help="Optional background music file. It will be looped and mixed at low volume."
    )
    parser.add_argument(
        "--sound-effect",
        help="Optional transition sound effect file used at each clip boundary.",
    )
    parser.add_argument(
        "--music-volume",
        type=float,
        default=0.18,
        help="Background music volume (0.0-1.0). Default: 0.18",
    )
    parser.add_argument(
        "--sfx-duration",
        type=float,
        default=0.30,
        help="Duration in seconds from start of transition SFX to use. Default: 0.30",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    clips = [Path(c) for c in args.clips]
    for clip in clips:
        if not clip.exists():
            parser.error(f"Clip not found: {clip}")

    output = Path(args.output)
    music = Path(args.music) if args.music else None
    sound_effect = Path(args.sound_effect) if args.sound_effect else None

    if music and not music.exists():
        parser.error(f"Music file not found: {music}")
    if sound_effect and not sound_effect.exists():
        parser.error(f"Sound effect file not found: {sound_effect}")
    if not 0.0 <= args.music_volume <= 1.0:
        parser.error("Music volume must be between 0.0 and 1.0")
    if args.sfx_duration <= 0:
        parser.error("SFX duration must be a positive number")

    ensure_ffmpeg_tools()

    with tempfile.TemporaryDirectory(prefix="yt-automation-") as tmp:
        concat_path = Path(tmp) / "clips.txt"
        build_concat_file(clips, concat_path)

        command = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_path)]

        music_index = None
        sfx_index = None

        if music:
            command.extend(["-stream_loop", "-1", "-i", str(music)])
            music_index = 1

        if sound_effect:
            command.extend(["-i", str(sound_effect)])
            sfx_index = 2 if music_index is not None else 1

        filter_parts = [
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
            "fps=30,eq=contrast=1.05:saturation=1.1,"
            "unsharp=5:5:0.8,format=yuv420p[vout]"
        ]

        audio_current = "a_base"
        filter_parts.append("[0:a]loudnorm[a_base]")

        if music_index is not None:
            filter_parts.append(f"[{music_index}:a]volume={args.music_volume}[music]")
            filter_parts.append(f"[{audio_current}][music]amix=inputs=2:duration=first[a_mix]")
            audio_current = "a_mix"

        if sfx_index is not None:
            times = transition_times(clips)
            sfx_labels = []
            for i, t in enumerate(times):
                delay_ms = int(t * 1000)
                label = f"sfx_{i}"
                filter_parts.append(
                    f"[{sfx_index}:a]atrim=0:{args.sfx_duration},"
                    f"asetpts=N/SR/TB,adelay={delay_ms}|{delay_ms}[{label}]"
                )
                sfx_labels.append(f"[{label}]")

            if sfx_labels:
                sfx_mix_inputs = f"[{audio_current}]" + "".join(sfx_labels)
                total_inputs = 1 + len(sfx_labels)
                filter_parts.append(
                    f"{sfx_mix_inputs}amix=inputs={total_inputs}:duration=first[aout]"
                )
                audio_current = "aout"

        if audio_current != "aout":
            filter_parts.append(f"[{audio_current}]anull[aout]")

        filter_complex = ";".join(filter_parts)

        command.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )

        run(command)

    print(f"Created edited video: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
