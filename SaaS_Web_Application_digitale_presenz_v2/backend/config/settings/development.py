from .base import *  # noqa: F403

DEBUG = True

# Browsable API is useful locally; production serves JSON only.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append("rest_framework.renderers.BrowsableAPIRenderer")  # noqa: F405
