"""Fitness TV music adapter package."""

from .base import (
    DEFAULT_MUSIC_SEARCH_LIMIT,
    DEFAULT_MUSIC_SEARCH_MEDIA_TYPES,
    MUSIC_SEARCH_MEDIA_TYPES,
    MAX_MUSIC_SEARCH_LIMIT,
    MIN_MUSIC_SEARCH_LIMIT,
    MusicAdapter,
    MusicAdapterInfo,
    clamp_search_limit,
)
from .registry import (
    async_music_adapters,
    async_music_provider_catalog,
    async_resolve_fitness_media,
    async_search_music,
)

__all__ = (
    "DEFAULT_MUSIC_SEARCH_LIMIT",
    "DEFAULT_MUSIC_SEARCH_MEDIA_TYPES",
    "MUSIC_SEARCH_MEDIA_TYPES",
    "MAX_MUSIC_SEARCH_LIMIT",
    "MIN_MUSIC_SEARCH_LIMIT",
    "MusicAdapter",
    "MusicAdapterInfo",
    "async_music_adapters",
    "async_music_provider_catalog",
    "async_resolve_fitness_media",
    "async_search_music",
    "clamp_search_limit",
)
