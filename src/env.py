import os
from dotenv import load_dotenv

load_dotenv()

PROFILE_VAR_NAME = "ENV"
VERSION_VAR_NAME = "VERSION"
TG_TOKEN_VAR_NAME = "TELEGRAM_TOKEN"

DEV_PROFILE_NAME = "DEV"
PROD_PROFILE_NAME = "PROD"


def getProfile():
    return os.environ.get(PROFILE_VAR_NAME, DEV_PROFILE_NAME)


def getVersion():
    return os.environ.get(VERSION_VAR_NAME, "none")


def getTelegramToken():
    if TG_TOKEN_VAR_NAME not in os.environ:
        raise EnvironmentError(f"{TG_TOKEN_VAR_NAME} env var does not exist")
    return os.environ.get(TG_TOKEN_VAR_NAME)


def isDevProfile():
    return getProfile() == DEV_PROFILE_NAME


def isProdProfile():
    return getProfile() == PROD_PROFILE_NAME
