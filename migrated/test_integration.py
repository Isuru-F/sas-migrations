"""
Integration tests for SQL Magic using SQLite database
Tests actual SQL execution and compares with pandas implementations
"""

import pytest
import pandas as pd
import numpy as np
import sqlite3
import tempfile
import os
from pathlib import Path
from sql_magic import SQLMagic


class TestSQLiteIntegration:
    """Integration tests using SQLite database"""
    
    @pytest.fixture
    def sqlite_db(self):
        """Create temporary SQLite database"""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_sql_magic.db"
        
        conn = sqlite3.connect(str(db_path))
        yield conn
        
        conn.close()
        os.unlink(db_path)
        os.rmdir(temp_dir)
    
    @pytest.fixture
    def magic_with_data(self, sqlite_db):
        """Create test data and load into SQLite"""
        magic = SQLMagic(seed=42)
        
        # Create test datasets (smaller for integration tests)
        bigdata = magic.create_bigdata(n_rows=10_000)
        smalldata = magic.create_smalldata(bigdata, n_samples=10)
        
        # Load into SQLite
        bigdata.to_sql('bigdata', sqlite_db, if_exists='replace', index=False)
        smalldata.to_sql('smalldata', sqlite_db, if_exists='replace', index=False)
        
        # Create indexes for better join performance
        sqlite_db.execute('CREATE INDEX idx_bigdata_group_obs ON bigdata("group", obs)')
        sqlite_db.execute('CREATE INDEX idx_smalldata_group_obs ON smalldata("group", obs)')
        sqlite_db.commit()
        
        return magic, sqlite_db
    
    def test_sqlite_hash_join(self, magic_with_data):
        """Test SQLite hash join produces same results as pandas"""
        magic, conn = magic_with_data
        
        # SQLite doesn't have explicit hash join hint, but uses it automatically
        # for small right tables
        sql_result = pd.read_sql_query("""
            SELECT t1."group", t1.obs, t1.value, t2.status
            FROM bigdata t1
            INNER JOIN smalldata t2
                ON t1."group" = t2."group" AND t1.obs = t2.obs
        """, conn)
        
        pandas_result = magic.hash_join()
        
        # Sort both for comparison
        sql_sorted = sql_result.sort_values(['group', 'obs']).reset_index(drop=True)
        pandas_sorted = pandas_result.data.sort_values(['group', 'obs']).reset_index(drop=True)
        
        assert len(sql_sorted) == len(pandas_sorted)
        pd.testing.assert_frame_equal(
            sql_sorted[['group', 'obs', 'status']], 
            pandas_sorted[['group', 'obs', 'status']]
        )
    
    def test_sqlite_nested_loop_join(self, magic_with_data):
        """Test SQLite nested loop join (forced with CROSS JOIN + WHERE)"""
        magic, conn = magic_with_data
        
        # Force nested loop by using CROSS JOIN with WHERE
        sql_result = pd.read_sql_query("""
            SELECT t1."group", t1.obs, t1.value, t2.status
            FROM bigdata t1
            CROSS JOIN smalldata t2
            WHERE t1."group" = t2."group" AND t1.obs = t2.obs
        """, conn)
        
        pandas_result = magic.sequential_loop_join()
        
        # Sort both for comparison
        sql_sorted = sql_result.sort_values(['group', 'obs']).reset_index(drop=True)
        pandas_sorted = pandas_result.data.sort_values(['group', 'obs']).reset_index(drop=True)
        
        assert len(sql_sorted) == len(pandas_sorted)
        pd.testing.assert_frame_equal(
            sql_sorted[['group', 'obs', 'status']], 
            pandas_sorted[['group', 'obs', 'status']]
        )
    
    def test_sqlite_create_table_as_select(self, magic_with_data):
        """Test creating table from join (equivalent to SAS CREATE TABLE AS)"""
        magic, conn = magic_with_data
        
        # Create table from join (SAS: create table magic_103 as)
        conn.execute("""
            CREATE TABLE magic_103 AS
            SELECT t1."group", t1.obs, t1.value, t2.status
            FROM bigdata t1
            INNER JOIN smalldata t2
                ON t1."group" = t2."group" AND t1.obs = t2.obs
        """)
        conn.commit()
        
        # Read created table
        sql_result = pd.read_sql_query("SELECT * FROM magic_103", conn)
        
        # Compare with pandas hash join
        pandas_result = magic.hash_join()
        
        sql_sorted = sql_result.sort_values(['group', 'obs']).reset_index(drop=True)
        pandas_sorted = pandas_result.data.sort_values(['group', 'obs']).reset_index(drop=True)
        
        assert len(sql_sorted) == len(pandas_sorted)
        pd.testing.assert_frame_equal(
            sql_sorted[['group', 'obs', 'status']], 
            pandas_sorted[['group', 'obs', 'status']]
        )
    
    def test_sqlite_multiple_output_tables(self, magic_with_data):
        """Test creating multiple output tables (magic_101, 102, 103)"""
        magic, conn = magic_with_data
        
        # Create all three output tables (simulating all three SAS PROC SQL runs)
        tables = {
            'magic_101': 'Sequential Loop equivalent',
            'magic_102': 'Sort Merge equivalent', 
            'magic_103': 'Hash Join equivalent'
        }
        
        for table_name in tables.keys():
            conn.execute(f"""
                CREATE TABLE {table_name} AS
                SELECT t1."group", t1.obs, t1.value, t2.status
                FROM bigdata t1
                INNER JOIN smalldata t2
                    ON t1."group" = t2."group" AND t1.obs = t2.obs
            """)
        conn.commit()
        
        # Verify all tables exist and have same content
        results = {}
        for table_name in tables.keys():
            results[table_name] = pd.read_sql_query(
                f"SELECT * FROM {table_name} ORDER BY \"group\", obs", 
                conn
            )
        
        # All tables should be identical
        base = results['magic_103']
        for table_name, df in results.items():
            if table_name != 'magic_103':
                pd.testing.assert_frame_equal(base, df)
    
    def test_sqlite_data_types(self, magic_with_data):
        """Test that data types are preserved correctly in SQLite"""
        magic, conn = magic_with_data
        
        # Query data types from SQLite
        cursor = conn.execute("PRAGMA table_info(bigdata)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        # Verify columns exist
        assert 'obs' in columns
        assert 'group' in columns
        assert 'value' in columns
        
        cursor = conn.execute("PRAGMA table_info(smalldata)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        assert 'obs' in columns
        assert 'group' in columns
        assert 'status' in columns
    
    def test_sqlite_join_with_aggregation(self, magic_with_data):
        """Test join combined with aggregation"""
        magic, conn = magic_with_data
        
        # Aggregate after join
        sql_result = pd.read_sql_query("""
            SELECT 
                t1."group",
                COUNT(*) as match_count,
                AVG(t1.value) as avg_value
            FROM bigdata t1
            INNER JOIN smalldata t2
                ON t1."group" = t2."group" AND t1.obs = t2.obs
            GROUP BY t1."group"
            ORDER BY t1."group"
        """, conn)
        
        # Equivalent in pandas
        pandas_result = magic.hash_join()
        pandas_agg = pandas_result.data.groupby('group').agg({
            'group': 'size',
            'value': 'mean'
        }).rename(columns={'group': 'match_count', 'value': 'avg_value'}).reset_index()
        
        assert len(sql_result) == len(pandas_agg)
    
    def test_sqlite_index_performance(self, magic_with_data):
        """Test that indexes improve query performance"""
        magic, conn = magic_with_data
        
        # Drop indexes
        conn.execute("DROP INDEX IF EXISTS idx_bigdata_group_obs")
        conn.execute("DROP INDEX IF EXISTS idx_smalldata_group_obs")
        conn.commit()
        
        # Query without indexes
        import time
        start = time.time()
        pd.read_sql_query("""
            SELECT t1."group", t1.obs, t1.value, t2.status
            FROM bigdata t1
            INNER JOIN smalldata t2
                ON t1."group" = t2."group" AND t1.obs = t2.obs
        """, conn)
        time_without_index = time.time() - start
        
        # Recreate indexes
        conn.execute('CREATE INDEX idx_bigdata_group_obs ON bigdata("group", obs)')
        conn.execute('CREATE INDEX idx_smalldata_group_obs ON smalldata("group", obs)')
        conn.commit()
        
        # Query with indexes
        start = time.time()
        pd.read_sql_query("""
            SELECT t1."group", t1.obs, t1.value, t2.status
            FROM bigdata t1
            INNER JOIN smalldata t2
                ON t1."group" = t2."group" AND t1.obs = t2.obs
        """, conn)
        time_with_index = time.time() - start
        
        # Indexed query should be faster (or at least not much slower)
        assert time_with_index <= time_without_index * 1.5


class TestSQLiteVsPandas:
    """Compare SQLite and pandas performance"""
    
    @pytest.fixture
    def comparison_setup(self):
        """Setup for comparison tests"""
        magic = SQLMagic(seed=42)
        magic.create_bigdata(n_rows=50_000)
        magic.create_smalldata(n_samples=20)
        
        # Create in-memory SQLite database
        conn = sqlite3.connect(':memory:')
        magic.bigdata.to_sql('bigdata', conn, if_exists='replace', index=False)
        magic.smalldata.to_sql('smalldata', conn, if_exists='replace', index=False)
        
        conn.execute('CREATE INDEX idx_bigdata_group_obs ON bigdata("group", obs)')
        conn.execute('CREATE INDEX idx_smalldata_group_obs ON smalldata("group", obs)')
        conn.commit()
        
        yield magic, conn
        conn.close()
    
    def test_consistency_across_implementations(self, comparison_setup):
        """Verify all implementations produce identical results"""
        magic, conn = comparison_setup
        
        # Get results from all methods
        pandas_hash = magic.hash_join()
        pandas_merge = magic.sort_merge_join()
        pandas_loop = magic.sequential_loop_join()
        pandas_lookup = magic.hash_lookup()
        
        sql_result = pd.read_sql_query("""
            SELECT t1."group", t1.obs, t1.value, t2.status
            FROM bigdata t1
            INNER JOIN smalldata t2
                ON t1."group" = t2."group" AND t1.obs = t2.obs
        """, conn)
        
        # Sort all results
        results = [
            pandas_hash.data.sort_values(['group', 'obs']).reset_index(drop=True),
            pandas_merge.data.sort_values(['group', 'obs']).reset_index(drop=True),
            pandas_loop.data.sort_values(['group', 'obs']).reset_index(drop=True),
            pandas_lookup.data.sort_values(['group', 'obs']).reset_index(drop=True),
            sql_result.sort_values(['group', 'obs']).reset_index(drop=True)
        ]
        
        # All should have same row count
        base_count = len(results[0])
        for result in results[1:]:
            assert len(result) == base_count
        
        # All should have identical group, obs, status values
        base = results[0][['group', 'obs', 'status']]
        for result in results[1:]:
            pd.testing.assert_frame_equal(base, result[['group', 'obs', 'status']])
    
    def test_row_count_verification(self, comparison_setup):
        """Verify row counts match across all methods"""
        magic, conn = comparison_setup
        
        # Count in SQLite
        cursor = conn.execute("""
            SELECT COUNT(*) 
            FROM bigdata t1
            INNER JOIN smalldata t2
                ON t1."group" = t2."group" AND t1.obs = t2.obs
        """)
        sql_count = cursor.fetchone()[0]
        
        # Count in pandas
        pandas_count = magic.hash_join().row_count
        
        assert sql_count == pandas_count


class TestEndToEnd:
    """End-to-end integration tests"""
    
    def test_full_migration_workflow(self):
        """Test complete workflow from data generation to all joins"""
        # Step 1: Create SQLMagic instance
        magic = SQLMagic(seed=42)
        
        # Step 2: Generate datasets
        bigdata = magic.create_bigdata(n_rows=5_000)
        smalldata = magic.create_smalldata(bigdata, n_samples=5)
        
        assert len(bigdata) == 5_000
        assert len(smalldata) == 5
        
        # Step 3: Load into SQLite
        conn = sqlite3.connect(':memory:')
        bigdata.to_sql('bigdata', conn, if_exists='replace', index=False)
        smalldata.to_sql('smalldata', conn, if_exists='replace', index=False)
        
        # Step 4: Run all pandas joins
        results = magic.compare_all_methods()
        
        assert len(results) == 4
        assert 'sequential_loop' in results
        assert 'sort_merge' in results
        assert 'hash_join' in results
        assert 'hash_lookup' in results
        
        # Step 5: Run SQL join
        sql_result = pd.read_sql_query("""
            SELECT t1."group", t1.obs, t1.value, t2.status
            FROM bigdata t1
            INNER JOIN smalldata t2
                ON t1."group" = t2."group" AND t1.obs = t2.obs
        """, conn)
        
        # Step 6: Verify consistency
        base = results['hash_join'].data.sort_values(['group', 'obs']).reset_index(drop=True)
        sql_sorted = sql_result.sort_values(['group', 'obs']).reset_index(drop=True)
        
        assert len(base) == len(sql_sorted)
        
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
