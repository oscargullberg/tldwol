from os import path, linesep
import asyncio

from .config import get_config

config = get_config()
WHISPER_CPP_DIR = config.whisper_cpp_dir_path
WHISPER_MODEL_PATH = config.whisper_model_path


async def _run_whisper(input_file_path):
    whisper_binary_path = path.join(WHISPER_CPP_DIR, "main")

    stderr_lines = []
    stdout_lines = []
    whisper_process = await asyncio.create_subprocess_exec(
        whisper_binary_path,
        "-m",
        WHISPER_MODEL_PATH,
        "-f",
        input_file_path,
        "-l",
        "auto",
        "-t",
        "10",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=WHISPER_CPP_DIR,
    )
    async for line in whisper_process.stdout:
        print(f"[whisper] stdout: {line.decode().strip()}")
        stdout_lines.append(line.decode().strip())

    async for line in whisper_process.stderr:
        stderr_lines.append(line.decode().strip())

    exit_code = await whisper_process.wait()

    print(f"[whisper] exitcode: {exit_code}")
    if exit_code != 0:
        print(stderr_lines)
        raise ValueError(f"whisper failed with code '{exit_code}'.")

    return stdout_lines


async def transcribe(file_path):
    cache_path = f"{file_path}-transcript.txt"
    if path.exists(cache_path):
        print("loading transcript from cache")
        with open(cache_path, "r") as f:
            return f.readlines()

    else:
        print("generating transcript")
        transcript_lines = await _run_whisper(file_path)
        with open(cache_path, "w+") as f:
            f.writelines(f"{line}{linesep}" for line in transcript_lines)
        print("generated and cached transcript")
        return transcript_lines
