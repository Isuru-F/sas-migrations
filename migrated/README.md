# SAS to Python Migration: sql_magic

This project migrates the SAS `sql_magic.sas` script to Python using SQLite, demonstrating different SQL join strategies and their performance characteristics.

## Overview

The migration implements:
- **Data Generation**: 25M row dataset with random data
- **Random Sampling**: 10-row lookup table 
- **Join Strategies**:
  - `magic_101`: Nested Loop Join
  - `magic_102`: Sort-Merge Join (with indexes)
  - `magic_103`: Hash Join (Python dictionary)
  - `hash_result`: SAS DATA step hash lookup equivalent

## Project Structure

```
migrated/
├── sql_magic.py              # Main migration script
├── sql_magic_config.py       # Configuration (can switch between test/full)
├── sql_magic_config_full.py  # Full 25M row configuration  
├── test_sql_magic.py         # Unit tests (36 tests)
├── test_integration.py       # Integration tests (22 tests)
├── requirements.txt          # Python dependencies
├── validation/               # Validation scripts directory
└── README.md                 # This file
```

## Requirements

- Python 3.10+
- numpy
- pytest
- pytest-cov

## Installation

```bash
cd migrated
pip install -r requirements.txt
```

## Usage

### Run the Migration Script

```bash
python3 sql_magic.py
```

This will:
1. Create SQLite database (`sql_magic_test.db` by default)
2. Generate bigdata table with random data
3. Create smalldata by sampling bigdata  
4. Execute 4 different join strategies
5. Verify all results match
6. Display timing and row counts

### Configuration

Edit `sql_magic_config.py` to adjust:
- `BIGDATA_ROWS`: Number of rows to generate (default: 100,000 for testing)
- `SMALLDATA_ROWS`: Number of samples (default: 10)
- `RANDOM_SEED`: For reproducibility (default: 42)
- `DB_NAME`: Database filename

For the full 25M row dataset, swap configs:
```bash
mv sql_magic_config.py sql_magic_config_test.py
mv sql_magic_config_full.py sql_magic_config.py
python3 sql_magic.py
```

## Testing

### Unit Tests

Run all unit tests (36 tests covering data generation, schema, joins, statistics):

```bash
python3 -m pytest test_sql_magic.py -v
```

Run with coverage report:

```bash
python3 -m pytest test_sql_magic.py --cov=sql_magic --cov-report=term-missing
```

Run specific test class:

```bash
python3 -m pytest test_sql_magic.py::TestJoinResults -v
```

### Integration Tests

Run end-to-end integration tests:

```bash
python3 -m pytest test_integration.py -v
```

Note: Integration tests will regenerate the database from scratch.

### Run All Tests

```bash
python3 -m pytest test_sql_magic.py test_integration.py -v
```

## Test Commands Summary

| Command | Description |
|---------|-------------|
| `python3 sql_magic.py` | Generate database and run all join strategies |
| `python3 -m pytest test_sql_magic.py -v` | Run 36 unit tests |
| `python3 -m pytest test_integration.py -v` | Run 22 integration tests |
| `python3 -m pytest test_sql_magic.py test_integration.py -v` | Run all tests |
| `python3 -m pytest --cov=sql_magic --cov-report=html` | Generate coverage report |
| `python3 -m py_compile sql_magic.py` | Verify Python syntax |
| `sqlite3 sql_magic_test.db "SELECT COUNT(*) FROM bigdata"` | Query database directly |

## Validation

Verify the migration:

```bash
# Check row counts
sqlite3 sql_magic_test.db "
SELECT 
    'bigdata' as table_name, COUNT(*) as row_count FROM bigdata
UNION ALL
SELECT 'smalldata', COUNT(*) FROM smalldata
UNION ALL  
SELECT 'magic_101', COUNT(*) FROM magic_101
UNION ALL
SELECT 'magic_102', COUNT(*) FROM magic_102
UNION ALL
SELECT 'magic_103', COUNT(*) FROM magic_103
UNION ALL
SELECT 'hash_result', COUNT(*) FROM hash_result;
"

# Verify all join results are identical
sqlite3 sql_magic_test.db "
SELECT COUNT(*) FROM (
    SELECT * FROM magic_101 
    EXCEPT 
    SELECT * FROM magic_102
);
"
# Should return 0
```

## Performance

With default configuration (100k rows):
- **Generation**: < 1 second
- **Sampling**: < 1 second
- **Joins**: < 1 second each
- **Total**: ~2-5 seconds

With full configuration (25M rows):
- **Generation**: ~60-120 seconds
- **Sampling**: < 1 second  
- **Joins**: Varies by strategy (nested loop slowest, hash fastest)
- **Total**: ~2-5 minutes

## Database Schema

```sql
CREATE TABLE bigdata (
    obs INTEGER,
    group_col INTEGER,
    value REAL
);

CREATE TABLE smalldata (
    obs INTEGER,
    group_col INTEGER,
    value REAL,
    status TEXT
);

CREATE TABLE magic_101 (
    group_col INTEGER,
    obs INTEGER,
    value REAL,
    status TEXT
);

-- magic_102, magic_103, hash_result have same schema as magic_101
```

## Troubleshooting

### Database not found error in tests
```bash
# Ensure database is created first
python3 sql_magic.py
```

### Import errors
```bash
# Install dependencies
pip install -r requirements.txt
```

### Permission errors
```bash
# Ensure write permissions in migrated/ directory
chmod +w .
```

### Out of memory (with 25M rows)
```bash
# Use smaller dataset by editing sql_magic_config.py
# Or increase BATCH_SIZE to reduce memory usage
```

## Migration from SAS

This Python implementation replicates the SAS `sql_magic.sas` behavior:

| SAS Feature | Python Equivalent |
|-------------|-------------------|
| `data bigdata;` | SQLite table creation + numpy generation |
| `call streaminit(42)` | `np.random.default_rng(42)` |
| `rand('integer', ...)` | `rng.integers(...)` |
| `rand('uniform')` | `rng.uniform(...)` |
| `point=` random access | `LIMIT 1 OFFSET n` |
| `PROC SQL MAGIC=101` | Basic INNER JOIN |
| `PROC SQL MAGIC=102` | INNER JOIN with indexes |
| `PROC SQL MAGIC=103` | Python dictionary hash join |
| SAS hash object | Python dict lookup |

## License

This is a migration project for demonstration purposes.

## Contact

For questions about this migration, refer to `/specs/sql_magic_migration_plan.md`.
