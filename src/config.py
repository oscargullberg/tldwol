from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llama_cpp_dir_path: str
    whisper_cpp_dir_path: str
    files_dl_dir_path: str = "downloads"
    llama_model_path: str

    model_config = SettingsConfigDict(env_file=".env")


_settings_instance = Settings()


def get_config():
    global _settings_instance
    _settings_instance = _settings_instance or Settings()
    return _settings_instance
