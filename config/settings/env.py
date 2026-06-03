from pathlib import Path

import environ


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

DOTENV_PATH = BASE_DIR / ".env"
environ.Env.read_env(DOTENV_PATH, overwrite=True)
