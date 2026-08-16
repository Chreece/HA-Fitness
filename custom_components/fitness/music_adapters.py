"""Compatibility facade for the per-adapter Fitness TV music package."""

from .music import (
    DEFAULT_MUSIC_SEARCH_LIMIT,
    DEFAULT_MUSIC_SEARCH_MEDIA_TYPES,
    MUSIC_SEARCH_MEDIA_TYPES,
    MAX_MUSIC_SEARCH_LIMIT,
    MIN_MUSIC_SEARCH_LIMIT,
    MusicAdapter,
    MusicAdapterInfo,
    async_music_adapters,
    async_music_provider_catalog,
    async_resolve_fitness_media,
    async_search_music,
    clamp_search_limit,
)
from .music.yt_dlp import FITNESS_YTDLP_PREFIX

__all__ = (
    "DEFAULT_MUSIC_SEARCH_LIMIT",
    "DEFAULT_MUSIC_SEARCH_MEDIA_TYPES",
    "MUSIC_SEARCH_MEDIA_TYPES",
    "FITNESS_YTDLP_PREFIX",
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
