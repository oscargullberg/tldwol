import asyncio
from yt_dlp import YoutubeDL
import aiohttp
from os.path import join as path_join, expanduser
import hashlib
import re
import yarl
from pathlib import Path
from .config import get_config

config = get_config()
DOWNLOAD_DIR = config.files_dl_dir_path


class DownloadStrategy:
    def __init__(self, test, handler):
        self.test = test
        self.handler = handler

    def is_match(self, url):
        return self.test(url)


def md5_encode(str):
    return hashlib.md5(str.encode()).hexdigest()


async def download_file(url, file_path):
    async with aiohttp.ClientSession(
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        },
        requote_redirect_url=False,
    ) as session:
        print(f"Starting download file from {url}")
        async with session.get(url) as response:
            print(response.status, "status")
            if response.status >= 400:
                body = await response.text()
                raise ValueError(
                    f"File download failed with status {response.status} and body '{body}'"
                )

            with open(file_path, "wb+") as f:
                while True:
                    chunk = await response.content.readany()
                    if not chunk:
                        break
                    f.write(chunk)
            print(f"Downloaded {file_path} from {url}")
            return file_path


async def download_youtube_audio(url):
    loop = asyncio.get_running_loop()

    def sync_download():
        ydl_opts = {"format": "bestaudio", "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s"}
        with YoutubeDL(ydl_opts) as ydl:
            print("downloading from yt")
            info = ydl.extract_info(url, download=False)
            ydl.download([url])
            return Path(DOWNLOAD_DIR) / f'{info["id"]}.{info["ext"]}'

    return await loop.run_in_executor(None, sync_download)


async def download_apple_podcast(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(yarl.URL(url, encoded=True)) as response:
            html = await response.text()
            pattern = r'assetUrl[^"]+":[^:]+"([^\\]+)'
            match = re.search(pattern, html)
            if match:
                episode_download_url = match.group(1)
                output_path = Path(DOWNLOAD_DIR) / f"{md5_encode(url)}.mp3"

                return await download_file(episode_download_url, output_path)
            raise ValueError("Apple podcast body parsing failed")


DOWNLOAD_STRATEGIES = [
    DownloadStrategy(
        test=lambda url: re.match(r"(https?://)?(www.)?youtube.com/watch\?v=", url),
        handler=download_youtube_audio,
    ),
    DownloadStrategy(
        test=lambda url: re.match(
            r"(https?://)?podcasts\.apple\.com/\w+/podcast/\w+/id\d+/?", url
        ),
        handler=download_apple_podcast,
    ),
    DownloadStrategy(
        test=lambda url: re.match(r"https?://.+", url), handler=download_file
    ),
]


def download_file_from_url(url):
    for strategy in DOWNLOAD_STRATEGIES:
        if strategy.is_match(url):
            return strategy.handler(url)
    raise ValueError(f"No matching strategy for URL: '{url}'.")
