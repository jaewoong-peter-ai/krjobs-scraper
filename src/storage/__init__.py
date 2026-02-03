"""Storage modules for job postings"""

from .local_storage import LocalStorage
from .supabase_storage import SupabaseStorage

__all__ = ["LocalStorage", "SupabaseStorage"]
