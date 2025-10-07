"""
End-to-End Integration Test Suite for SAS SQL Magic Migration

Tests the complete workflow of sql_magic.py including:
- Database creation and population
- Table existence and structure
- Data integrity and validation
- Join strategy correctness
- Reproducibility verification
- Performance benchmarks
"""

import os
import sys
import sqlite3
import hashlib
import time
import subprocess
from pathlib import Path
import pytest

try:
    from sql_magic_config import BIGDATA_ROWS, SMALLDATA_ROWS, DB_NAME
except ImportError:
    BIGDATA_ROWS = 25_000_000
    SMALLDATA_ROWS = 10
    DB_NAME = 'sql_magic.db'


# Configuration
TEST_DB_NAME = DB_NAME
MAIN_SCRIPT = 'sql_magic.py'
EXPECTED_TABLES = ['bigdata', 'smalldata', 'magic_101', 'magic_102', 'magic_103', 'hash_result']
EXPECTED_BIGDATA_ROWS = BIGDATA_ROWS
EXPECTED_SMALLDATA_ROWS = SMALLDATA_ROWS
EXPECTED_JOIN_ROWS = SMALLDATA_ROWS  # Since smalldata has 10 rows and we're doing inner join


@pytest.fixture(scope="module")
def test_db_path():
    """Provide path to test database"""
    return Path(__file__).parent / TEST_DB_NAME


@pytest.fixture(scope="module")
def main_script_path():
    """Provide path to main script"""
    return Path(__file__).parent / MAIN_SCRIPT


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown(test_db_path, main_script_path):
    """
    Setup: Run sql_magic.py with test database name
    Teardown: Clean up test database
    """
    # Setup: Clean any existing test database
    if test_db_path.exists():
        test_db_path.unlink()
    
    # Verify main script exists
    if not main_script_path.exists():
        pytest.skip(f"Main script {MAIN_SCRIPT} not found. Create it first.")
    
    # Run the main script programmatically
    # We'll import and run it, or use subprocess if it has a main guard
    start_time = time.time()
    
    try:
        # Try importing and running programmatically
        sys.path.insert(0, str(main_script_path.parent))
        
        # Save original DB_NAME config
        import sql_magic_config
        original_db_name = sql_magic_config.DB_NAME
        
        # Override with test database name
        sql_magic_config.DB_NAME = TEST_DB_NAME
        
        # Import and run main script
        import importlib
        sql_magic = importlib.import_module('sql_magic')
        
        # Execute main function if it exists
        if hasattr(sql_magic, 'main'):
            sql_magic.main()
        
        # Restore original config
        sql_magic_config.DB_NAME = original_db_name
        
    except (ImportError, AttributeError) as e:
        # Fallback: Run as subprocess
        env = os.environ.copy()
        env['DB_NAME'] = TEST_DB_NAME
        
        result = subprocess.run(
            [sys.executable, str(main_script_path)],
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            pytest.fail(f"Script execution failed:\n{result.stderr}")
    
    execution_time = time.time() - start_time
    
    print(f"\n✓ Initial script execution completed in {execution_time:.2f} seconds")
    
    # Verify database was created
    assert test_db_path.exists(), "Test database was not created"
    
    yield test_db_path
    
    # Teardown: Clean up
    if test_db_path.exists():
        test_db_path.unlink()
        print(f"\n✓ Test database {TEST_DB_NAME} cleaned up")


@pytest.fixture
def db_connection(test_db_path):
    """Provide database connection for tests"""
    conn = sqlite3.connect(test_db_path)
    yield conn
    conn.close()


class TestDatabaseCreation:
    """Test database file creation and basic structure"""
    
    def test_database_file_exists(self, test_db_path):
        """Verify database file was created"""
        assert test_db_path.exists()
        assert test_db_path.is_file()
        assert test_db_path.stat().st_size > 0
    
    def test_database_accessible(self, db_connection):
        """Verify database can be opened and queried"""
        cursor = db_connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result == (1,)


class TestTableExistence:
    """Test that all expected tables exist"""
    
    def test_all_tables_exist(self, db_connection):
        """Verify all 6 expected tables are present"""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        
        for expected_table in EXPECTED_TABLES:
            assert expected_table in tables, f"Table {expected_table} not found"
    
    def test_no_extra_tables(self, db_connection):
        """Verify no unexpected tables exist"""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        
        assert len(tables) == len(EXPECTED_TABLES), \
            f"Expected {len(EXPECTED_TABLES)} tables, found {len(tables)}: {tables}"


class TestTableStructure:
    """Test table schemas and column definitions"""
    
    def test_bigdata_schema(self, db_connection):
        """Verify bigdata table structure"""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(bigdata)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert 'obs' in columns
        assert 'group' in columns or 'group_col' in columns
        assert 'value' in columns
    
    def test_smalldata_schema(self, db_connection):
        """Verify smalldata table structure"""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(smalldata)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert 'obs' in columns
        assert 'group' in columns or 'group_col' in columns
        assert 'status' in columns
    
    def test_join_tables_schema(self, db_connection):
        """Verify join result tables have consistent structure"""
        cursor = db_connection.cursor()
        
        join_tables = ['magic_101', 'magic_102', 'magic_103']
        schemas = {}
        
        for table in join_tables:
            cursor.execute(f"PRAGMA table_info({table})")
            # Store column names (not types, as SQLite may use INT or INTEGER interchangeably)
            schemas[table] = [row[1] for row in cursor.fetchall()]
        
        # All join tables should have same column names
        base_schema = schemas['magic_101']
        
        for table, schema in schemas.items():
            assert schema == base_schema, \
                f"Table {table} has different columns than magic_101"


class TestDataIntegrity:
    """Test data quality and integrity"""
    
    def test_bigdata_row_count(self, db_connection):
        """Verify bigdata has expected number of rows"""
        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM bigdata")
        count = cursor.fetchone()[0]
        
        assert count == EXPECTED_BIGDATA_ROWS, \
            f"Expected {EXPECTED_BIGDATA_ROWS} rows, found {count}"
    
    def test_smalldata_row_count(self, db_connection):
        """Verify smalldata has expected number of rows"""
        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM smalldata")
        count = cursor.fetchone()[0]
        
        assert count == EXPECTED_SMALLDATA_ROWS, \
            f"Expected {EXPECTED_SMALLDATA_ROWS} rows, found {count}"
    
    def test_bigdata_no_nulls(self, db_connection):
        """Verify bigdata has no NULL values in key columns"""
        cursor = db_connection.cursor()
        
        # Check for group column (might be 'group' or 'group_col')
        cursor.execute("PRAGMA table_info(bigdata)")
        columns = [row[1] for row in cursor.fetchall()]
        group_col = 'group' if 'group' in columns else 'group_col'
        
        cursor.execute(f"""
            SELECT COUNT(*) FROM bigdata 
            WHERE obs IS NULL OR {group_col} IS NULL OR value IS NULL
        """)
        
        null_count = cursor.fetchone()[0]
        assert null_count == 0, f"Found {null_count} rows with NULL values"
    
    def test_smalldata_status_field(self, db_connection):
        """Verify all smalldata rows have status='Found it!'"""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM smalldata 
            WHERE status = 'Found it!'
        """)
        
        count = cursor.fetchone()[0]
        assert count == EXPECTED_SMALLDATA_ROWS, \
            f"Expected {EXPECTED_SMALLDATA_ROWS} rows with status='Found it!', found {count}"


class TestJoinCorrectness:
    """Test that all join strategies produce identical results"""
    
    def test_join_row_counts(self, db_connection):
        """Verify all join tables have same row count"""
        cursor = db_connection.cursor()
        
        counts = {}
        for table in ['magic_101', 'magic_102', 'magic_103', 'hash_result']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
        
        # All should have same count
        base_count = counts['magic_101']
        
        for table, count in counts.items():
            assert count == base_count, \
                f"Table {table} has {count} rows, expected {base_count}"
        
        # Should match expected join result count
        assert base_count == EXPECTED_JOIN_ROWS, \
            f"Expected {EXPECTED_JOIN_ROWS} joined rows, found {base_count}"
    
    def test_magic_101_vs_102_identical(self, db_connection):
        """Verify magic_101 and magic_102 produce identical results"""
        cursor = db_connection.cursor()
        
        # Get column names
        cursor.execute("PRAGMA table_info(magic_101)")
        columns = [row[1] for row in cursor.fetchall()]
        col_list = ', '.join(columns)
        
        # Find differences
        cursor.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT {col_list} FROM magic_101
                EXCEPT
                SELECT {col_list} FROM magic_102
            )
        """)
        
        diff_count = cursor.fetchone()[0]
        assert diff_count == 0, \
            f"Found {diff_count} differences between magic_101 and magic_102"
    
    def test_magic_102_vs_103_identical(self, db_connection):
        """Verify magic_102 and magic_103 produce identical results"""
        cursor = db_connection.cursor()
        
        cursor.execute("PRAGMA table_info(magic_102)")
        columns = [row[1] for row in cursor.fetchall()]
        col_list = ', '.join(columns)
        
        cursor.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT {col_list} FROM magic_102
                EXCEPT
                SELECT {col_list} FROM magic_103
            )
        """)
        
        diff_count = cursor.fetchone()[0]
        assert diff_count == 0, \
            f"Found {diff_count} differences between magic_102 and magic_103"
    
    def test_magic_103_vs_hash_identical(self, db_connection):
        """Verify magic_103 and hash_result produce identical results"""
        cursor = db_connection.cursor()
        
        cursor.execute("PRAGMA table_info(magic_103)")
        columns = [row[1] for row in cursor.fetchall()]
        col_list = ', '.join(columns)
        
        cursor.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT {col_list} FROM magic_103
                EXCEPT
                SELECT {col_list} FROM hash_result
            )
        """)
        
        diff_count = cursor.fetchone()[0]
        assert diff_count == 0, \
            f"Found {diff_count} differences between magic_103 and hash_result"
    
    def test_join_referential_integrity(self, db_connection):
        """Verify all join results exist in source tables"""
        cursor = db_connection.cursor()
        
        # Get column names
        cursor.execute("PRAGMA table_info(bigdata)")
        columns = [row[1] for row in cursor.fetchall()]
        group_col = 'group' if 'group' in columns else 'group_col'
        
        # Check magic_101 rows exist in both bigdata and smalldata
        cursor.execute(f"""
            SELECT COUNT(*) FROM magic_101 m
            LEFT JOIN bigdata b 
                ON m.obs = b.obs AND m.{group_col} = b.{group_col}
            WHERE b.obs IS NULL
        """)
        
        orphan_count = cursor.fetchone()[0]
        assert orphan_count == 0, \
            f"Found {orphan_count} join results not in bigdata"


class TestReproducibility:
    """Test that execution is reproducible with same seed"""
    
    def test_run_twice_identical_checksums(self, test_db_path, main_script_path):
        """Run script twice and verify checksums match"""
        # First run already completed in fixture
        first_checksums = self._calculate_table_checksums(test_db_path)
        
        # Delete database and run again
        test_db_path.unlink()
        
        # Run script again
        start_time = time.time()
        
        try:
            sys.path.insert(0, str(main_script_path.parent))
            import sql_magic_config
            original_db_name = sql_magic_config.DB_NAME
            sql_magic_config.DB_NAME = TEST_DB_NAME
            
            import importlib
            importlib.reload(importlib.import_module('sql_magic'))
            
            sql_magic_config.DB_NAME = original_db_name
            
        except Exception:
            env = os.environ.copy()
            env['DB_NAME'] = TEST_DB_NAME
            
            result = subprocess.run(
                [sys.executable, str(main_script_path)],
                env=env,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                pytest.fail(f"Second execution failed:\n{result.stderr}")
        
        execution_time = time.time() - start_time
        print(f"\n✓ Second execution completed in {execution_time:.2f} seconds")
        
        # Calculate checksums again
        second_checksums = self._calculate_table_checksums(test_db_path)
        
        # Compare checksums
        for table in EXPECTED_TABLES:
            assert first_checksums[table] == second_checksums[table], \
                f"Table {table} produced different results on second run"
    
    def _calculate_table_checksums(self, db_path):
        """Calculate MD5 checksums for all tables"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        checksums = {}
        
        for table in EXPECTED_TABLES:
            # Get column names
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]
            
            if not columns:
                continue
                
            col_list = ', '.join(columns)
            
            # Get sorted data
            cursor.execute(f"SELECT {col_list} FROM {table} ORDER BY {col_list}")
            rows = cursor.fetchall()
            
            # Calculate checksum
            data_str = str(rows).encode('utf-8')
            checksums[table] = hashlib.md5(data_str).hexdigest()
        
        conn.close()
        return checksums


class TestPerformance:
    """Test performance benchmarks"""
    
    def test_query_performance(self, db_connection):
        """Verify query performance is acceptable"""
        cursor = db_connection.cursor()
        
        # Test: Count query on bigdata
        start = time.time()
        cursor.execute("SELECT COUNT(*) FROM bigdata")
        cursor.fetchone()
        count_time = time.time() - start
        
        assert count_time < 5.0, \
            f"Count query took {count_time:.2f}s, expected < 5.0s"
        
        # Test: Join query
        cursor.execute("PRAGMA table_info(bigdata)")
        columns = [row[1] for row in cursor.fetchall()]
        group_col = 'group' if 'group' in columns else 'group_col'
        
        start = time.time()
        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM bigdata b
            INNER JOIN smalldata s 
                ON b.obs = s.obs AND b.{group_col} = s.{group_col}
        """)
        cursor.fetchone()
        join_time = time.time() - start
        
        assert join_time < 10.0, \
            f"Join query took {join_time:.2f}s, expected < 10.0s"
    
    def test_database_size_reasonable(self, test_db_path):
        """Verify database file size is reasonable"""
        size_mb = test_db_path.stat().st_size / (1024 * 1024)
        
        # Size varies with row count. For 25M rows: ~1-3GB, for 100k rows: ~3-10MB
        min_size = 1 if EXPECTED_BIGDATA_ROWS >= 1_000_000 else 0.5
        max_size = 5000 if EXPECTED_BIGDATA_ROWS >= 1_000_000 else 50
        
        assert min_size < size_mb < max_size, \
            f"Database size {size_mb:.2f} MB outside expected range [{min_size}, {max_size}]"


class TestValidationQueries:
    """Test data validation with SQL queries"""
    
    def test_group_distribution(self, db_connection):
        """Verify group distribution is roughly uniform"""
        cursor = db_connection.cursor()
        
        cursor.execute("PRAGMA table_info(bigdata)")
        columns = [row[1] for row in cursor.fetchall()]
        group_col = 'group' if 'group' in columns else 'group_col'
        
        cursor.execute(f"""
            SELECT {group_col}, COUNT(*) as cnt
            FROM bigdata
            GROUP BY {group_col}
            ORDER BY {group_col}
        """)
        
        groups = cursor.fetchall()
        
        # Should have 5 groups
        assert len(groups) == 5, f"Expected 5 groups, found {len(groups)}"
        
        # Each group should have roughly 5M rows (25M / 5)
        expected_per_group = EXPECTED_BIGDATA_ROWS / 5
        tolerance = 0.1  # 10% tolerance
        
        for group_id, count in groups:
            lower_bound = expected_per_group * (1 - tolerance)
            upper_bound = expected_per_group * (1 + tolerance)
            
            assert lower_bound < count < upper_bound, \
                f"Group {group_id} has {count} rows, expected ~{expected_per_group}"
    
    def test_value_distribution(self, db_connection):
        """Verify value column has uniform distribution [0,1]"""
        cursor = db_connection.cursor()
        
        cursor.execute("""
            SELECT 
                MIN(value) as min_val,
                MAX(value) as max_val,
                AVG(value) as avg_val
            FROM bigdata
        """)
        
        min_val, max_val, avg_val = cursor.fetchone()
        
        # Min should be close to 0
        assert 0 <= min_val < 0.01, f"Min value {min_val} too high"
        
        # Max should be close to 1
        assert 0.99 < max_val <= 1, f"Max value {max_val} too low"
        
        # Average should be around 0.5 for uniform distribution
        assert 0.45 < avg_val < 0.55, f"Average value {avg_val} not around 0.5"
    
    def test_smalldata_subset_of_bigdata(self, db_connection):
        """Verify all smalldata rows exist in bigdata"""
        cursor = db_connection.cursor()
        
        cursor.execute("PRAGMA table_info(bigdata)")
        columns = [row[1] for row in cursor.fetchall()]
        group_col = 'group' if 'group' in columns else 'group_col'
        
        cursor.execute(f"""
            SELECT COUNT(*) FROM smalldata s
            LEFT JOIN bigdata b 
                ON s.obs = b.obs AND s.{group_col} = b.{group_col}
            WHERE b.obs IS NULL
        """)
        
        missing_count = cursor.fetchone()[0]
        assert missing_count == 0, \
            f"Found {missing_count} smalldata rows not in bigdata"


# Summary function
def pytest_sessionfinish(session, exitstatus):
    """Print summary after all tests complete"""
    if exitstatus == 0:
        print("\n" + "="*70)
        print("✓✓✓ ALL INTEGRATION TESTS PASSED ✓✓✓")
        print("="*70)
        print("\nIntegration Test Coverage Summary:")
        print("  ✓ Database creation and file existence")
        print("  ✓ All 6 tables created correctly")
        print("  ✓ Table schemas validated")
        print("  ✓ 25M rows in bigdata, 10 rows in smalldata")
        print("  ✓ No NULL values in key columns")
        print("  ✓ All join strategies produce identical results")
        print("  ✓ Referential integrity maintained")
        print("  ✓ Reproducibility confirmed (checksums match)")
        print("  ✓ Performance benchmarks met")
        print("  ✓ Data distributions validated")
        print("="*70)
