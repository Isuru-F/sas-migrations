#!/usr/bin/env python3
"""
SAS to Python Migration: sql_magic.sas
This script migrates the SAS sql_magic.sas functionality to Python using SQLite.
Demonstrates different join strategies: nested loop, sort-merge, and hash joins.
"""

import sqlite3
import sys
import time
from pathlib import Path
import numpy as np

try:
    from sql_magic_config import (
        RANDOM_SEED, BIGDATA_ROWS, SMALLDATA_ROWS, BATCH_SIZE,
        DB_NAME, GROUP_MIN, GROUP_MAX, OBS_MIN, OBS_MAX
    )
except ImportError:
    RANDOM_SEED = 42
    BIGDATA_ROWS = 25_000_000
    SMALLDATA_ROWS = 10
    BATCH_SIZE = 100_000
    DB_NAME = 'sql_magic.db'
    GROUP_MIN = 1
    GROUP_MAX = 5
    OBS_MIN = 1
    OBS_MAX = 1_000_000_000


class SQLiteDatabase:
    """Handles SQLite database operations for the SAS migration."""
    
    def __init__(self, db_path):
        """Initialize database connection."""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Connect to SQLite database."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        print(f"Connected to database: {self.db_path}")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed")
    
    def create_bigdata_table(self):
        """Create the bigdata table with schema matching SAS dataset."""
        self.cursor.execute('DROP TABLE IF EXISTS bigdata')
        self.cursor.execute('''
            CREATE TABLE bigdata (
                obs INTEGER,
                group_col INTEGER,
                value REAL
            )
        ''')
        self.conn.commit()
        print("Created bigdata table")
    
    def generate_bigdata(self):
        """Generate 25M rows of random data matching SAS DATA step logic."""
        print(f"Generating {BIGDATA_ROWS:,} rows of bigdata...")
        start_time = time.time()
        
        rng = np.random.default_rng(RANDOM_SEED)
        
        total_batches = (BIGDATA_ROWS + BATCH_SIZE - 1) // BATCH_SIZE
        
        for batch_num in range(total_batches):
            batch_start = batch_num * BATCH_SIZE
            current_batch_size = min(BATCH_SIZE, BIGDATA_ROWS - batch_start)
            
            obs_vals = rng.integers(OBS_MIN, OBS_MAX + 1, size=current_batch_size)
            group_vals = rng.integers(GROUP_MIN, GROUP_MAX + 1, size=current_batch_size)
            value_vals = rng.uniform(0, 1, size=current_batch_size)
            
            data = list(zip(obs_vals.tolist(), group_vals.tolist(), value_vals.tolist()))
            self.cursor.executemany('INSERT INTO bigdata VALUES (?, ?, ?)', data)
            self.conn.commit()
            
            if (batch_num + 1) % 10 == 0 or batch_num == total_batches - 1:
                print(f"  Inserted batch {batch_num + 1}/{total_batches} ({batch_start + current_batch_size:,} rows)")
        
        elapsed = time.time() - start_time
        print(f"bigdata generation completed in {elapsed:.2f} seconds")
        
        self.cursor.execute('SELECT COUNT(*) FROM bigdata')
        count = self.cursor.fetchone()[0]
        print(f"bigdata row count: {count:,}")
    
    def create_smalldata_table(self):
        """Create smalldata by randomly sampling 10 rows from bigdata."""
        print(f"Creating smalldata with {SMALLDATA_ROWS} random samples...")
        start_time = time.time()
        
        self.cursor.execute('SELECT COUNT(*) FROM bigdata')
        nobs = self.cursor.fetchone()[0]
        
        rng = np.random.default_rng(RANDOM_SEED)
        random_positions = rng.integers(1, nobs + 1, size=SMALLDATA_ROWS)
        
        self.cursor.execute('DROP TABLE IF EXISTS smalldata')
        self.cursor.execute('''
            CREATE TABLE smalldata (
                obs INTEGER,
                group_col INTEGER,
                value REAL,
                status TEXT
            )
        ''')
        
        for pos in random_positions:
            self.cursor.execute(f'''
                SELECT obs, group_col, value FROM bigdata LIMIT 1 OFFSET {pos - 1}
            ''')
            row = self.cursor.fetchone()
            if row:
                self.cursor.execute(
                    "INSERT INTO smalldata VALUES (?, ?, ?, 'Found it!')",
                    (row[0], row[1], row[2])
                )
        
        self.conn.commit()
        
        elapsed = time.time() - start_time
        print(f"smalldata creation completed in {elapsed:.2f} seconds")
        
        self.cursor.execute('SELECT COUNT(*) FROM smalldata')
        count = self.cursor.fetchone()[0]
        print(f"smalldata row count: {count}")
    
    def magic_101_nested_loop_join(self):
        """MAGIC=101: Sequential/Nested Loop Join simulation via SQL."""
        print("\n" + "="*60)
        print("MAGIC=101: Sequential Loop Join")
        print("="*60)
        start_time = time.time()
        
        self.cursor.execute('DROP TABLE IF EXISTS magic_101')
        self.cursor.execute('''
            CREATE TABLE magic_101 AS
            SELECT t1.group_col, t1.obs, t1.value, t2.status
            FROM bigdata t1
            INNER JOIN smalldata t2
            ON t1.group_col = t2.group_col AND t1.obs = t2.obs
        ''')
        self.conn.commit()
        
        elapsed = time.time() - start_time
        self.cursor.execute('SELECT COUNT(*) FROM magic_101')
        count = self.cursor.fetchone()[0]
        
        print(f"Completed in {elapsed:.2f} seconds")
        print(f"Result rows: {count}")
    
    def magic_102_sort_merge_join(self):
        """MAGIC=102: Sort-Merge Join with indexes."""
        print("\n" + "="*60)
        print("MAGIC=102: Sort-Merge Join (with indexes)")
        print("="*60)
        start_time = time.time()
        
        print("Creating indexes...")
        index_start = time.time()
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_bigdata_join ON bigdata(group_col, obs)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_smalldata_join ON smalldata(group_col, obs)')
        self.conn.commit()
        index_elapsed = time.time() - index_start
        print(f"Indexes created in {index_elapsed:.2f} seconds")
        
        self.cursor.execute('DROP TABLE IF EXISTS magic_102')
        self.cursor.execute('''
            CREATE TABLE magic_102 AS
            SELECT t1.group_col, t1.obs, t1.value, t2.status
            FROM bigdata t1
            INNER JOIN smalldata t2
            ON t1.group_col = t2.group_col AND t1.obs = t2.obs
        ''')
        self.conn.commit()
        
        elapsed = time.time() - start_time
        self.cursor.execute('SELECT COUNT(*) FROM magic_102')
        count = self.cursor.fetchone()[0]
        
        print(f"Completed in {elapsed:.2f} seconds (including index creation)")
        print(f"Result rows: {count}")
    
    def magic_103_hash_join(self):
        """MAGIC=103: Hash Join using Python dictionary."""
        print("\n" + "="*60)
        print("MAGIC=103: Hash Join (Python dictionary)")
        print("="*60)
        start_time = time.time()
        
        print("Building hash table from smalldata...")
        hash_start = time.time()
        self.cursor.execute('SELECT group_col, obs, status FROM smalldata')
        hash_table = {(row[0], row[1]): row[2] for row in self.cursor.fetchall()}
        hash_elapsed = time.time() - hash_start
        print(f"Hash table built in {hash_elapsed:.2f} seconds ({len(hash_table)} entries)")
        
        self.cursor.execute('DROP TABLE IF EXISTS magic_103')
        self.cursor.execute('''
            CREATE TABLE magic_103 (
                group_col INTEGER,
                obs INTEGER,
                value REAL,
                status TEXT
            )
        ''')
        
        print("Probing bigdata against hash table...")
        probe_start = time.time()
        self.cursor.execute('SELECT group_col, obs, value FROM bigdata')
        
        batch = []
        matched_count = 0
        for row in self.cursor.fetchall():
            key = (row[0], row[1])
            if key in hash_table:
                batch.append((row[0], row[1], row[2], hash_table[key]))
                matched_count += 1
                if len(batch) >= 10000:
                    self.cursor.executemany('INSERT INTO magic_103 VALUES (?, ?, ?, ?)', batch)
                    self.conn.commit()
                    batch = []
        
        if batch:
            self.cursor.executemany('INSERT INTO magic_103 VALUES (?, ?, ?, ?)', batch)
            self.conn.commit()
        
        probe_elapsed = time.time() - probe_start
        elapsed = time.time() - start_time
        
        self.cursor.execute('SELECT COUNT(*) FROM magic_103')
        count = self.cursor.fetchone()[0]
        
        print(f"Probing completed in {probe_elapsed:.2f} seconds")
        print(f"Total time: {elapsed:.2f} seconds")
        print(f"Result rows: {count}")
    
    def hash_result(self):
        """Pure Python hash lookup mimicking SAS DATA step hash."""
        print("\n" + "="*60)
        print("DATA Step Hash Join (Python implementation)")
        print("="*60)
        start_time = time.time()
        
        print("Loading smalldata into hash lookup...")
        self.cursor.execute('SELECT group_col, obs, status FROM smalldata')
        lookup = {(row[0], row[1]): row[2] for row in self.cursor.fetchall()}
        print(f"Hash lookup loaded with {len(lookup)} entries")
        
        self.cursor.execute('DROP TABLE IF EXISTS hash_result')
        self.cursor.execute('''
            CREATE TABLE hash_result (
                group_col INTEGER,
                obs INTEGER,
                value REAL,
                status TEXT
            )
        ''')
        
        print("Processing bigdata with hash lookup...")
        self.cursor.execute('SELECT group_col, obs, value FROM bigdata')
        
        matches = []
        for row in self.cursor.fetchall():
            status = lookup.get((row[0], row[1]))
            if status is not None:
                matches.append((row[0], row[1], row[2], status))
        
        if matches:
            self.cursor.executemany('INSERT INTO hash_result VALUES (?, ?, ?, ?)', matches)
            self.conn.commit()
        
        elapsed = time.time() - start_time
        self.cursor.execute('SELECT COUNT(*) FROM hash_result')
        count = self.cursor.fetchone()[0]
        
        print(f"Completed in {elapsed:.2f} seconds")
        print(f"Result rows: {count}")
    
    def verify_results(self):
        """Verify that all join methods produce identical results."""
        print("\n" + "="*60)
        print("Verifying result consistency")
        print("="*60)
        
        tables = ['magic_101', 'magic_102', 'magic_103', 'hash_result']
        counts = {}
        
        for table in tables:
            try:
                self.cursor.execute(f'SELECT COUNT(*) FROM {table}')
                counts[table] = self.cursor.fetchone()[0]
            except sqlite3.OperationalError:
                counts[table] = None
        
        print("Row counts:")
        for table, count in counts.items():
            if count is not None:
                print(f"  {table}: {count:,}")
            else:
                print(f"  {table}: TABLE NOT FOUND")
        
        unique_counts = set(c for c in counts.values() if c is not None)
        if len(unique_counts) == 1:
            print("\n✓ All join methods produced identical row counts")
        else:
            print("\n✗ WARNING: Row counts differ between methods")
        
        try:
            self.cursor.execute('''
                SELECT COUNT(*) FROM (
                    SELECT * FROM magic_101
                    EXCEPT
                    SELECT * FROM magic_102
                )
            ''')
            diff_count = self.cursor.fetchone()[0]
            if diff_count == 0:
                print("✓ magic_101 and magic_102 results are identical")
            else:
                print(f"✗ magic_101 and magic_102 differ by {diff_count} rows")
        except sqlite3.OperationalError as e:
            print(f"Could not compare magic_101 and magic_102: {e}")


def main():
    """Main execution function."""
    print("="*60)
    print("SAS sql_magic.sas Migration to Python")
    print("="*60)
    print()
    
    script_dir = Path(__file__).parent
    db_path = script_dir / DB_NAME
    
    if db_path.exists():
        print(f"Removing existing database: {db_path}")
        db_path.unlink()
    
    db = SQLiteDatabase(db_path)
    
    try:
        db.connect()
        
        db.create_bigdata_table()
        db.generate_bigdata()
        
        db.create_smalldata_table()
        
        db.magic_101_nested_loop_join()
        
        db.magic_102_sort_merge_join()
        
        db.magic_103_hash_join()
        
        db.hash_result()
        
        db.verify_results()
        
        print("\n" + "="*60)
        print("Migration completed successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
