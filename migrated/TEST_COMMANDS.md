# Test Commands - Quick Reference

## Prerequisites

Install dependencies first:

```bash
pip install pandas numpy pytest sqlalchemy
```

Or using requirements.txt:

```bash
pip install -r requirements.txt
```

---

## Running Tests

### 1. Unit Tests

Test core Python functionality and join methods:

```bash
# Run all unit tests
python3 -m pytest test_sql_magic.py -v

# Run all unit tests with summary
python3 -m pytest test_sql_magic.py -v --tb=short

# Run specific test class
python3 -m pytest test_sql_magic.py::TestJoinMethods -v

# Run specific test
python3 -m pytest test_sql_magic.py::TestJoinMethods::test_hash_join -v
```

**Expected Result:**
```
============================== 18 passed in 10.96s ==============================
```

---

### 2. Integration Tests

Test SQLite database integration and SQL compatibility:

```bash
# Run all integration tests
python3 -m pytest test_integration.py -v

# Run all integration tests with summary
python3 -m pytest test_integration.py -v --tb=short

# Run specific test class
python3 -m pytest test_integration.py::TestSQLiteIntegration -v

# Run specific test
python3 -m pytest test_integration.py::TestSQLiteIntegration::test_sqlite_hash_join -v
```

**Expected Result:**
```
============================== 10 passed in 0.49s ==============================
```

---

### 3. All Tests (Recommended)

Run complete test suite (unit + integration):

```bash
# Run all tests
python3 -m pytest test_sql_magic.py test_integration.py -v

# Run all tests with concise output
python3 -m pytest test_sql_magic.py test_integration.py -v --tb=line

# Run all tests with timing information
python3 -m pytest test_sql_magic.py test_integration.py -v --durations=10
```

**Expected Result:**
```
============================== 28 passed in 11.45s ==============================
```

---

## Running the Main Application

Execute the migration demo:

```bash
# Run with 1M rows (default demo size)
python3 sql_magic.py

# For quick testing, edit sql_magic.py and change:
# n_rows = 100_000  # Smaller dataset for faster demo
```

**Expected Output:**
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

VERIFYING CONSISTENCY...
✓ Sequential Loop (magic=101): MATCH
✓ Sort Merge (magic=102): MATCH
✓ Hash Lookup (DATA step): MATCH
```

---

## Test Options & Flags

### Common pytest Options

```bash
# Verbose output
pytest -v

# Very verbose (show test docstrings)
pytest -vv

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf

# Show slowest tests
pytest --durations=10

# Parallel execution (requires pytest-xdist)
pytest -n auto

# Code coverage (requires pytest-cov)
pytest --cov=sql_magic --cov-report=html
```

### Filtering Tests

```bash
# Run tests matching pattern
pytest -k "hash_join"

# Run tests NOT matching pattern
pytest -k "not slow"

# Run by marker (if defined)
pytest -m "unit"
```

---

## Verification Checklist

After making changes, run this checklist:

```bash
# 1. Verify code runs without errors
python3 sql_magic.py

# 2. Run unit tests
python3 -m pytest test_sql_magic.py -v

# 3. Run integration tests
python3 -m pytest test_integration.py -v

# 4. Check for any warnings
python3 -m pytest test_sql_magic.py test_integration.py -v -W error

# 5. (Optional) Check code coverage
python3 -m pytest test_sql_magic.py test_integration.py --cov=sql_magic --cov-report=term-missing
```

---

## Troubleshooting

### Tests Failing

```bash
# Clear cache and rerun
rm -rf .pytest_cache __pycache__
python3 -m pytest test_sql_magic.py test_integration.py -v

# Run with full traceback
python3 -m pytest test_sql_magic.py test_integration.py -vv --tb=long

# Run single failing test with debug
python3 -m pytest test_sql_magic.py::TestJoinMethods::test_hash_join -vv -s
```

### Import Errors

```bash
# Verify Python version
python3 --version  # Should be 3.8+

# Reinstall dependencies
pip install --upgrade pandas numpy pytest sqlalchemy

# Check installed packages
pip list | grep -E "pandas|numpy|pytest|sqlalchemy"
```

### Memory Issues

```bash
# Reduce dataset size in sql_magic.py
# Change: n_rows = 1_000_000
# To:     n_rows = 100_000

# Then rerun
python3 sql_magic.py
```

---

## Quick Test Summary

| Command | Tests | Duration | Purpose |
|---------|-------|----------|---------|
| `pytest test_sql_magic.py -v` | 18 | ~11s | Unit tests |
| `pytest test_integration.py -v` | 10 | ~0.5s | Integration tests |
| `pytest test_*.py -v` | 28 | ~11s | All tests |
| `python3 sql_magic.py` | N/A | ~3s | Demo execution |

---

## Test Coverage Summary

### Unit Tests (test_sql_magic.py)
- ✅ Data generation (6 tests)
- ✅ Join methods (5 tests)
- ✅ Edge cases (4 tests)
- ✅ Performance (2 tests)
- ✅ Data structures (1 test)

### Integration Tests (test_integration.py)
- ✅ SQLite compatibility (7 tests)
- ✅ Pandas vs SQL consistency (2 tests)
- ✅ End-to-end workflow (1 test)

**Total: 28 tests, 100% passing**
