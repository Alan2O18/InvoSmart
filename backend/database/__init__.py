# Initialize database module externally.
from .core import Base, init_db, AsyncSessionLocal, SyncSessionLocal, get_global_db_path
