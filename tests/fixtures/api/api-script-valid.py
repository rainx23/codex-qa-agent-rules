import os

METHOD = "post"
URL_OR_PATH = "https://example.invalid/api/waybill/list"
PARAMETERS = ("isAnalysis",)
REQUIRED_ENVIRONMENT_VARIABLES = ("API_BASE_URL", "API_TOKEN")


def validate_response(response):
    assert response["content"]["code"] == 0
    assert response["content"]["msg"] == "OK"


def required_environment():
    return {name: os.environ[name] for name in REQUIRED_ENVIRONMENT_VARIABLES}
