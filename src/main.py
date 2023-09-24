from fastapi import FastAPI
from os.path import join as path_join
from os import linesep, path
import asyncio
import time
import importlib
from .downloader import download_file_from_url
from .config import get_config


config = get_config()
LLAMA_CPP_DIR = config.llama_cpp_dir_path
WHISPER_CPP_DIR = config.whisper_cpp_dir_path
LLAMA_MODEL_PATH = config.llama_model_path


def chunk_list(lst, chunk_size, min_chunk_size):
    chunks, temp_chunk = [], []

    for i, item in enumerate(lst):
        temp_chunk.append(item)
        if len(temp_chunk) == chunk_size or i == len(lst) - 1:
            if len(temp_chunk) < min_chunk_size and chunks:
                chunks[-1].extend(temp_chunk)
            else:
                chunks.append(temp_chunk)
            temp_chunk = []

    return chunks


async def summarize_transcript_chunk(chunk):
    instruction = f"Summarize the content below, capturing all essential elements such as key points, subjects, events, and insights. Include significant years. Use the style of a university professor taking notes. Content: '{chunk}'."
    prompt = f"Below is an instruction that describes a task. Write a response that appropriately completes the request.\n\n### Instruction:\n{instruction}\n\n### Response:\n"
    summary_lines = await run_llama(prompt)
    return linesep.join(summary_lines)


async def summarize_summaries(joined_summaries):
    instruction = f"Merge the provided sub-summaries into a single, cohesive summary that encompasses all critical elements. Rectify translation errors and inconsistencies. Use the style of a university professor presenting research findings. Content: '{joined_summaries}'.,"
    prompt = f"Below is an instruction that describes a task. Write a response that appropriately completes the request.\n\n### Instruction:\n{instruction}\n\n### Response:\n"
    summary_lines = await run_llama(prompt)
    return linesep.join(summary_lines)


async def run_ffmpeg(input_file_path, output_file_path):
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


async def run_whisper(input_file_path):
    whisper_binary_path = path_join(WHISPER_CPP_DIR, "main")
    model_file_name = "ggml-large.bin"
    stderr_lines = []
    stdout_lines = []
    whisper_process = await asyncio.create_subprocess_exec(
        whisper_binary_path,
        "-m",
        f"models/{model_file_name}",
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


async def run_llama(prompt: str):
    stderr_lines = []
    stdout_lines = []
    response_index_start = -1
    end_of_prompt_line_start = "### Response:"

    llama_process = await asyncio.create_subprocess_exec(
        path_join(LLAMA_CPP_DIR, "main"),
        "--temp",
        "0.25",
        "--top-k",
        "20",
        "-c",
        "4096",
        "-n",
        "4096",
        "-m",
        LLAMA_MODEL_PATH,
        "--prompt",
        prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=LLAMA_CPP_DIR,
    )

    async for line in llama_process.stdout:
        processed_line = line.decode().strip()
        if end_of_prompt_line_start in processed_line:
            response_index_start = len(stdout_lines) + 1
        stdout_lines.append(processed_line)
        print(processed_line)

    async for line in llama_process.stderr:
        decoded = line.decode().strip()
        stderr_lines.append(decoded)
        if "error" in decoded:
            print(f"[llama.cpp] err: {decoded}")

    exit_code = await llama_process.wait()

    print(f"[llama.cpp] exitcode: {exit_code}")
    if exit_code != 0:
        print(stderr_lines)
        raise ValueError(f"llama failed with exit code {exit_code}")

    return stdout_lines[response_index_start:]


async def get_create_transcript(file_path):
    cache_path = f"{file_path}-transcript.txt"
    if path.exists(cache_path):
        print("loading transcript from cache")
        with open(cache_path, "r") as f:
            return f.readlines()

    else:
        print("generating transcript")
        transcript_lines = await run_whisper(file_path)
        lines_with_lineseps = list(map(lambda l: l + linesep, transcript_lines))
        with open(cache_path, "w+") as f:
            f.writelines(lines_with_lineseps)
        print("generated and cached transcript")
        return transcript_lines


app = FastAPI()


@app.get("/")
async def index(url: str):
    time_start = time.time()
    dl_file_path = await download_file_from_url(url)
    print(dl_file_path, "dl path")

    print("converting to wav")
    wav_file_path = f"{dl_file_path}.wav"
    await run_ffmpeg(dl_file_path, wav_file_path)
    print("converted to wav")

    transcript_lines = await get_create_transcript(wav_file_path)
    print("line count: ", len(transcript_lines))

    print("chunking transcript")
    transcript_chunks = chunk_list(transcript_lines, 70, 20)
    print(f"chunked transcript, {len(transcript_chunks)} chunks")

    chunk_summaries = []
    for chunk in transcript_chunks:
        summary = await summarize_transcript_chunk(linesep.join(chunk))
        chunk_summaries.append(summary)

    print("generating summary of summaries")
    tldr = await summarize_summaries(
        f"{linesep} Partial summary: {linesep}".join(chunk_summaries)
    )
    print("generated summary of summaries")
    time_delta = time.time() - time_start
    print(f"execution time, s: {time_delta}")
    return {"summary": tldr}


def start():
    uvicorn = importlib.import_module("uvicorn")
    uvicorn.run("src.main:app", reload=True)
