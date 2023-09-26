import asyncio


async def _run_ffmpeg(input_file_path, output_file_path):
    binary_path = "ffmpeg"
    stderr_lines = []
    ffmpeg_process = await asyncio.create_subprocess_exec(
        binary_path,
        "-i",
        f"{input_file_path}",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        f"{output_file_path}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    async for line in ffmpeg_process.stdout:
        print(f"[ffmpeg] stdout: {line.decode().strip()}")

    async for line in ffmpeg_process.stderr:
        print(f"[ffmpeg] stderr: {line.decode().strip()}")
        stderr_lines.append(line.decode().strip())

    exit_code = await ffmpeg_process.wait()
    if exit_code != 0:
        print(stderr_lines)
        raise ValueError("ffmpeg failed with exitcode '{exit_code}'")


async def convert_to_wav(input_file_path, output_file_path=None):
    output_file_path = output_file_path or f"{input_file_path}.wav"
    await _run_ffmpeg(input_file_path, output_file_path)
    return output_file_path
