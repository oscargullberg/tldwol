from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    llama_cpp_dir_path: str
    whisper_cpp_dir_path: str
    files_dl_dir_path: str = "downloads"
    llama_model_path: str
    whisper_model_path: str

    model_config = SettingsConfigDict(env_file=".env")


_settings_instance = None


def get_config() -> AppSettings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = AppSettings()
    return _settings_instance
