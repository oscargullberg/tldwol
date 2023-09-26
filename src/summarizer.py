from os import linesep, path
import asyncio

from .config import get_config


config = get_config()
LLAMA_CPP_DIR = config.llama_cpp_dir_path
LLAMA_MODEL_PATH = config.llama_model_path


def _chunk_list(lst, chunk_size, min_chunk_size):
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


async def _run_llama(prompt: str):
    stderr_lines = []
    stdout_lines = []
    response_index_start = -1
    end_of_prompt_line_start = "### Response:"

    llama_process = await asyncio.create_subprocess_exec(
        path.join(LLAMA_CPP_DIR, "main"),
        "--temp",
        "0.25",
        "-c",
        "4096",
        "-n",
        "4096",
        "--top-k",
        "25",
        "--repeat_penalty",
        "1.20",
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


async def _summarize_transcript_chunk(chunk):
    instruction = f"Summarize the content in a bullet list. Make sure to include the essential subjects, events and historical years. Write it from the viewpoint of an objective observer"
    prompt = f"Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.\n ### Instruction:\n{instruction}\n\n### Input:\n{chunk}\n\n ### Response:\n\n"
    summary_lines = await _run_llama(prompt)
    return linesep.join(summary_lines)


async def _summarize_summaries(joined_summaries):
    instruction = f"Revise the content to create a objective summary divided into paragraphs that retains all information. Write it in the style of an academic review without refering to it as such."
    prompt = f"Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request. \n ### Instruction:\n{instruction}\n\n### Input:\n'{joined_summaries}\n\n### Response:\n\n"
    summary_lines = await _run_llama(prompt)
    return linesep.join(summary_lines)


async def summarize(text_lines):
    print("line count: ", len(text_lines))

    print("chunking text lines")
    ## Hack, rough guess to not hit context limit :))
    transcript_chunks = _chunk_list(text_lines, 60, 20)
    print(f"chunked text lines into {len(transcript_chunks)} chunks")

    chunk_summaries = []
    for chunk in transcript_chunks:
        summary = await _summarize_transcript_chunk(linesep.join(chunk))
        chunk_summaries.append(summary)

    print("generating summary of summaries")
    summary_of_summaries = await _summarize_summaries(
        f"{linesep}".join(chunk_summaries)
    )
    print("generated summary of summaries")
    return summary_of_summaries.lstrip()
