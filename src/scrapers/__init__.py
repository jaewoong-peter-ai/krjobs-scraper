"""Scraper modules for job sites"""

from .base import BaseScraper
from .kowork import KoworkScraper
from .komate import KomateScraper
from .klik import KlikScraper

__all__ = ["BaseScraper", "KoworkScraper", "KomateScraper", "KlikScraper"]
