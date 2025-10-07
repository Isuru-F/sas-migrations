"""Test configuration with smaller data size for faster testing."""
RANDOM_SEED = 42
BIGDATA_ROWS = 100_000  # Reduced from 25M for testing
SMALLDATA_ROWS = 10
BATCH_SIZE = 10_000
DB_NAME = 'sql_magic_test.db'
GROUP_MIN = 1
GROUP_MAX = 5
OBS_MIN = 1
OBS_MAX = 1_000_000_000
