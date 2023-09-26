from fastapi import FastAPI
import time
import importlib

from .downloader import download_file_from_url
from .wavconverter import convert_to_wav
from .transcriber import transcribe
from .summarizer import summarize


app = FastAPI()


@app.get("/")
async def index(url: str):
    time_start = time.time()

    dl_file_path = await download_file_from_url(url)
    wav_file_path = await convert_to_wav(dl_file_path)
    transcript_lines = await transcribe(wav_file_path)
    summary = await summarize(transcript_lines)

    time_delta = time.time() - time_start
    print(f"execution time, s: {time_delta}")
    return {"summary": summary}


def start():
    uvicorn = importlib.import_module("uvicorn")
    uvicorn.run("src.main:app", reload=True)
