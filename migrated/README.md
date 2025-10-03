# SQL Magic - Python Migration

Python implementation of SAS SQL join optimization techniques, migrated from `source/sql_magic.sas`.

## Overview

This project demonstrates three SQL join strategies and their Python equivalents:
- **Sequential Loop Join** (SAS magic=101)
- **Sort Merge Join** (SAS magic=102)
- **Hash Join** (SAS magic=103)
- **Hash-based Lookup** (SAS DATA step hash)

## Requirements

- Python 3.8+
- pandas
- numpy
- pytest (for testing)
- sqlalchemy (for integration tests)

## Installation

```bash
pip install -r requirements.txt
```

Or install individual packages:

```bash
pip install pandas numpy pytest sqlalchemy
```

## Project Structure

```
migrated/
├── sql_magic.py           # Main implementation
├── test_sql_magic.py      # Unit tests
├── test_integration.py    # SQLite integration tests
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Usage

### Running the Demo

Execute the main script to see all join methods in action:

```bash
python3 sql_magic.py
```

This will:
1. Generate 1M row synthetic dataset (`bigdata`)
2. Sample 10 rows for lookup (`smalldata`)
3. Execute all four join strategies
4. Compare performance and verify consistency

**Sample Output:**
```
Creating bigdata with 1,000,000 rows...
Created bigdata in 0.01s, Memory: 22.89 MB

============================================================
PERFORMANCE COMPARISON
============================================================
Method                         Time (s)     Rows       Memory (KB)
------------------------------------------------------------
Sequential Loop (magic=101)    0.0086       10         0.93
Sort Merge (magic=102)         0.2865       10         0.93
Hash Join (magic=103)          0.0407       10         0.93
Hash Lookup (DATA step)        2.2013       10         0.88
============================================================
```

### Using as a Library

```python
from sql_magic import SQLMagic

# Initialize with seed for reproducibility
magic = SQLMagic(seed=42)

# Create datasets
bigdata = magic.create_bigdata(n_rows=100_000)
smalldata = magic.create_smalldata(bigdata, n_samples=10)

# Run individual join methods
result = magic.hash_join()

print(f"Matched {result.row_count} rows in {result.execution_time:.4f}s")
print(result.data.head())

# Compare all methods
results = magic.compare_all_methods()
```

## Testing

### Running Unit Tests

Unit tests verify core functionality and join correctness:

```bash
# Run all unit tests
python3 -m pytest test_sql_magic.py -v

# Run specific test class
python3 -m pytest test_sql_magic.py::TestJoinMethods -v

# Run with coverage
python3 -m pytest test_sql_magic.py --cov=sql_magic --cov-report=html
```

**Test Coverage:**
- ✅ Data generation (shape, ranges, reproducibility)
- ✅ All join methods (sequential, merge, hash, lookup)
- ✅ Result consistency across methods
- ✅ Edge cases (no matches, multiple matches)
- ✅ Performance characteristics

**Expected Output:**
```
============================= test session starts ==============================
collected 18 items

test_sql_magic.py::TestDataGeneration::test_create_bigdata_shape PASSED  [  5%]
test_sql_magic.py::TestDataGeneration::test_create_bigdata_ranges PASSED [ 11%]
...
============================== 18 passed in 10.96s ==============================
```

### Running Integration Tests

Integration tests use SQLite database to verify SQL compatibility:

```bash
# Run all integration tests
python3 -m pytest test_integration.py -v

# Run specific test class
python3 -m pytest test_integration.py::TestSQLiteIntegration -v

# Run with verbose output
python3 -m pytest test_integration.py -v -s
```

**Test Coverage:**
- ✅ SQLite hash join compatibility
- ✅ CREATE TABLE AS SELECT (SAS equivalent)
- ✅ Multiple output tables (magic_101, 102, 103)
- ✅ Index performance optimization
- ✅ Pandas vs SQL consistency
- ✅ End-to-end workflow

**Expected Output:**
```
============================= test session starts ==============================
collected 10 items

test_integration.py::TestSQLiteIntegration::test_sqlite_hash_join PASSED [ 10%]
test_integration.py::TestSQLiteIntegration::test_sqlite_nested_loop_join PASSED [ 20%]
...
============================== 10 passed in 0.49s ==============================
```

### Running All Tests

```bash
# Run all tests (unit + integration)
python3 -m pytest test_sql_magic.py test_integration.py -v

# Run with summary
python3 -m pytest test_sql_magic.py test_integration.py -v --tb=short

# Run with timing
python3 -m pytest test_sql_magic.py test_integration.py -v --durations=10
```

**Expected Output:**
```
============================= test session starts ==============================
collected 28 items

test_sql_magic.py::TestDataGeneration::test_create_bigdata_shape PASSED
...
test_integration.py::TestEndToEnd::test_full_migration_workflow PASSED

============================== 28 passed in 11.45s ==============================
```

## Performance Characteristics

### Join Method Comparison

| Method | SAS Equivalent | Complexity | Memory | Best Use Case |
|--------|---------------|-----------|--------|---------------|
| Sequential Loop | magic=101 | O(n×m) | Low | Small lookup tables |
| Sort Merge | magic=102 | O(n log n) | Medium | Large datasets, limited memory |
| Hash Join | magic=103 | O(n+m) | High | Modern systems with RAM |
| Hash Lookup | DATA step hash | O(n) | Medium | Custom filtering logic |

### Benchmark Results (1M rows)

On MacBook Pro M1 (16GB RAM):

```
Method                         Time (s)     Memory (MB)
--------------------------------------------------------
Sequential Loop (magic=101)    0.0086       0.93
Sort Merge (magic=102)         0.2865       0.93
Hash Join (magic=103)          0.0407       0.93
Hash Lookup (DATA step)        2.2013       0.88
```

**Observations:**
- Sequential loop fastest for tiny lookup tables (10 rows)
- Hash join optimal for moderate datasets
- Sort merge has overhead from sorting
- Hash lookup has overhead from apply() iteration

## Migration Notes

### From SAS to Python

#### Data Generation
```sas
/* SAS */
data bigdata;
    call streaminit(42);
    do i = 1 to 25000000;
        obs   = rand('integer', 1, 1000000000);
        group = rand('integer', 1, 5);
        value = rand('uniform');
        output;
    end;
run;
```

```python
# Python
magic = SQLMagic(seed=42)
bigdata = magic.create_bigdata(n_rows=25_000_000)
```

#### Hash Join
```sas
/* SAS */
proc sql magic=103;
    create table magic_103 as 
        select t1.group, t1.obs, t1.value, t2.status
        from bigdata as t1
        INNER JOIN smalldata as t2
        ON t1.group=t2.group AND t1.obs=t2.obs;
quit;
```

```python
# Python
result = magic.hash_join()
magic_103 = result.data
```

#### SQLite
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('database.db')
bigdata.to_sql('bigdata', conn, if_exists='replace', index=False)
smalldata.to_sql('smalldata', conn, if_exists='replace', index=False)

magic_103 = pd.read_sql_query("""
    SELECT t1."group", t1.obs, t1.value, t2.status
    FROM bigdata t1
    INNER JOIN smalldata t2
        ON t1."group" = t2."group" AND t1.obs = t2.obs
""", conn)
```

## Advanced Usage

### Custom Dataset Sizes

```python
# Large-scale testing (requires more RAM)
magic = SQLMagic(seed=42)
bigdata = magic.create_bigdata(n_rows=50_000_000)
smalldata = magic.create_smalldata(bigdata, n_samples=100)

# Compare methods
results = magic.compare_all_methods()
```

### Filtering Specific Join Methods

```python
# Only run fast methods
magic = SQLMagic(seed=42)
magic.create_bigdata(n_rows=10_000_000)
magic.create_smalldata(n_samples=50)

hash_result = magic.hash_join()
loop_result = magic.sequential_loop_join()

# Skip slower methods
```

### Exporting Results

```python
# Export to CSV
result = magic.hash_join()
result.data.to_csv('magic_103.csv', index=False)

# Export to Parquet
result.data.to_parquet('magic_103.parquet', index=False)

# Export to SQLite
import sqlite3
conn = sqlite3.connect('output.db')
result.data.to_sql('magic_103', conn, if_exists='replace', index=False)
```

## Troubleshooting

### Memory Issues

If you encounter memory errors with large datasets:

```python
# Reduce dataset size
magic.create_bigdata(n_rows=1_000_000)  # Instead of 25M

# Use chunking for very large datasets
for chunk in pd.read_csv('large_file.csv', chunksize=100_000):
    # Process in chunks
    pass
```

### Performance Issues

```python
# Ensure numpy/pandas use optimized BLAS
import numpy as np
np.show_config()

# Use hash join for best performance
result = magic.hash_join()  # Fastest for small right table
```

### Test Failures

```bash
# Clear pytest cache
rm -rf .pytest_cache __pycache__

# Run tests with verbose output
python3 -m pytest test_sql_magic.py -vv

# Run specific failing test
python3 -m pytest test_sql_magic.py::TestJoinMethods::test_hash_join -vv
```

## References

- [Original SAS Code](../source/sql_magic.sas)
- [Migration Plan](../specs/sql_magic_migration_plan.md)
- [MWSUG-2012-S109: Add a Little Magic to Your Joins](https://www.mwsug.org/proceedings/2012/S1/MWSUG-2012-S109.pdf)
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

## License

Migrated from SAS code by Stu Sztukowski  
Migration Date: 2025-10-03

## Contributing

To add new join strategies or optimizations:

1. Add implementation to `sql_magic.py`
2. Add unit tests to `test_sql_magic.py`
3. Add integration tests to `test_integration.py`
4. Update this README
5. Run all tests to verify
