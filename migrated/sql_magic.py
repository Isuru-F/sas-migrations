"""
SQL Magic - Python Migration from SAS
Demonstrates different join strategies and their performance characteristics.

Migrated from: source/sql_magic.sas
Original Author: Stu Sztukowski
Migration Date: 2025-10-03
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any
import time
from dataclasses import dataclass


@dataclass
class JoinResult:
    """Result of a join operation with metadata"""
    data: pd.DataFrame
    method: str
    execution_time: float
    memory_usage: int
    row_count: int


class SQLMagic:
    """
    Implements various join strategies equivalent to SAS magic options:
    - Sequential Loop Join (magic=101)
    - Sort Merge Join (magic=102)
    - Hash Join (magic=103)
    - Hash-based lookup (DATA step equivalent)
    """
    
    def __init__(self, seed: int = 42):
        """
        Initialize SQL Magic with random seed for reproducibility.
        
        Args:
            seed: Random seed (default: 42 for reproducibility)
        """
        self.seed = seed
        np.random.seed(seed)
        self.bigdata = None
        self.smalldata = None
        
    def create_bigdata(self, n_rows: int = 25_000_000) -> pd.DataFrame:
        """
        Create synthetic test dataset equivalent to SAS bigdata.
        
        SAS equivalent:
            data bigdata;
                call streaminit(42);
                do i = 1 to 25000000;
                    obs   = rand('integer', 1, 1000000000);
                    group = rand('integer', 1, 5);
                    value = rand('uniform');
                    output;
                end;
            run;
        
        Args:
            n_rows: Number of rows to generate (default: 25M)
            
        Returns:
            DataFrame with columns: obs, group, value
        """
        print(f"Creating bigdata with {n_rows:,} rows...")
        start_time = time.time()
        
        self.bigdata = pd.DataFrame({
            'obs': np.random.randint(1, 1_000_000_001, size=n_rows),
            'group': np.random.randint(1, 6, size=n_rows),
            'value': np.random.uniform(0, 1, size=n_rows)
        })
        
        elapsed = time.time() - start_time
        memory_mb = self.bigdata.memory_usage(deep=True).sum() / 1024**2
        print(f"Created bigdata in {elapsed:.2f}s, Memory: {memory_mb:.2f} MB")
        
        return self.bigdata
    
    def create_smalldata(self, bigdata: pd.DataFrame = None, n_samples: int = 10) -> pd.DataFrame:
        """
        Create small lookup dataset by sampling from bigdata.
        
        SAS equivalent:
            data smalldata; 
                call streaminit(42);
                if(0) then set bigdata nobs=nobs;
                status = 'Found it!';
                do i=1 to 10;
                    n=rand('uniform', 1, nobs); 
                    set bigdata point=n;
                    output; 
                end;
                stop;
                drop i value;
            run;
        
        Args:
            bigdata: Source dataset to sample from
            n_samples: Number of samples to draw (default: 10)
            
        Returns:
            DataFrame with columns: obs, group, status
        """
        if bigdata is None:
            bigdata = self.bigdata
            
        if bigdata is None:
            raise ValueError("bigdata must be created first or provided as argument")
        
        print(f"Creating smalldata with {n_samples} samples...")
        
        # Sample random rows (equivalent to point= access)
        sampled = bigdata.sample(n=n_samples, random_state=self.seed)
        
        self.smalldata = pd.DataFrame({
            'obs': sampled['obs'].values,
            'group': sampled['group'].values,
            'status': ['Found it!'] * n_samples
        })
        
        print(f"Created smalldata with {len(self.smalldata)} rows")
        
        return self.smalldata
    
    def sequential_loop_join(self, 
                            bigdata: pd.DataFrame = None, 
                            smalldata: pd.DataFrame = None) -> JoinResult:
        """
        Sequential Loop Join (SAS magic=101)
        
        Simulates nested loop join by iterating through small table
        and filtering large table for each iteration.
        
        SAS equivalent:
            proc sql magic=101;
                create table magic_101 as 
                    select t1.group, t1.obs, t1.value, t2.status
                    from bigdata as t1
                    INNER JOIN smalldata as t2
                    ON t1.group=t2.group AND t1.obs=t2.obs;
            quit;
        
        Returns:
            JoinResult with matched rows
        """
        if bigdata is None:
            bigdata = self.bigdata
        if smalldata is None:
            smalldata = self.smalldata
            
        print("Performing Sequential Loop Join (magic=101)...")
        start_time = time.time()
        
        result_frames = []
        
        # Nested loop: for each row in small table, filter big table
        for _, small_row in smalldata.iterrows():
            matched = bigdata[
                (bigdata['group'] == small_row['group']) & 
                (bigdata['obs'] == small_row['obs'])
            ].copy()
            matched['status'] = small_row['status']
            result_frames.append(matched)
        
        result_df = pd.concat(result_frames, ignore_index=True) if result_frames else pd.DataFrame()
        
        execution_time = time.time() - start_time
        memory_usage = result_df.memory_usage(deep=True).sum()
        
        print(f"Sequential Loop Join completed in {execution_time:.4f}s, {len(result_df)} rows matched")
        
        return JoinResult(
            data=result_df,
            method="Sequential Loop (magic=101)",
            execution_time=execution_time,
            memory_usage=memory_usage,
            row_count=len(result_df)
        )
    
    def sort_merge_join(self,
                       bigdata: pd.DataFrame = None,
                       smalldata: pd.DataFrame = None) -> JoinResult:
        """
        Sort Merge Join (SAS magic=102)
        
        Sorts both tables and performs merge join.
        
        SAS equivalent:
            proc sql magic=102;
                create table magic_102 as 
                    select t1.group, t1.obs, t1.value, t2.status
                    from bigdata as t1
                    INNER JOIN smalldata as t2
                    ON t1.group=t2.group AND t1.obs=t2.obs;
            quit;
        
        Returns:
            JoinResult with matched rows
        """
        if bigdata is None:
            bigdata = self.bigdata
        if smalldata is None:
            smalldata = self.smalldata
            
        print("Performing Sort Merge Join (magic=102)...")
        start_time = time.time()
        
        # Sort both datasets by join keys
        bigdata_sorted = bigdata.sort_values(['group', 'obs'])
        smalldata_sorted = smalldata.sort_values(['group', 'obs'])
        
        # Perform merge on sorted data
        result_df = pd.merge(
            bigdata_sorted,
            smalldata_sorted,
            on=['group', 'obs'],
            how='inner',
            sort=False  # Already sorted
        )
        
        execution_time = time.time() - start_time
        memory_usage = result_df.memory_usage(deep=True).sum()
        
        print(f"Sort Merge Join completed in {execution_time:.4f}s, {len(result_df)} rows matched")
        
        return JoinResult(
            data=result_df,
            method="Sort Merge (magic=102)",
            execution_time=execution_time,
            memory_usage=memory_usage,
            row_count=len(result_df)
        )
    
    def hash_join(self,
                 bigdata: pd.DataFrame = None,
                 smalldata: pd.DataFrame = None) -> JoinResult:
        """
        Hash Join (SAS magic=103)
        
        Uses pandas merge which implements hash join for small right tables.
        
        SAS equivalent:
            proc sql magic=103;
                create table magic_103 as 
                    select t1.group, t1.obs, t1.value, t2.status
                    from bigdata as t1
                    INNER JOIN smalldata as t2
                    ON t1.group=t2.group AND t1.obs=t2.obs;
            quit;
        
        Returns:
            JoinResult with matched rows
        """
        if bigdata is None:
            bigdata = self.bigdata
        if smalldata is None:
            smalldata = self.smalldata
            
        print("Performing Hash Join (magic=103)...")
        start_time = time.time()
        
        # Standard merge - pandas uses hash join for small right table
        result_df = pd.merge(
            bigdata,
            smalldata,
            on=['group', 'obs'],
            how='inner'
        )
        
        execution_time = time.time() - start_time
        memory_usage = result_df.memory_usage(deep=True).sum()
        
        print(f"Hash Join completed in {execution_time:.4f}s, {len(result_df)} rows matched")
        
        return JoinResult(
            data=result_df,
            method="Hash Join (magic=103)",
            execution_time=execution_time,
            memory_usage=memory_usage,
            row_count=len(result_df)
        )
    
    def hash_lookup(self,
                   bigdata: pd.DataFrame = None,
                   smalldata: pd.DataFrame = None) -> JoinResult:
        """
        Hash-based lookup using dictionary (DATA step hash equivalent)
        
        SAS equivalent:
            data hash;
                set bigdata;
                if(_N_ = 1) then do;
                    dcl hash lookup(dataset: 'smalldata');
                        lookup.defineKey('group', 'obs');
                        lookup.defineData('status');
                    lookup.defineDone();
                end;
                if(lookup.Find() = 0);
            run;
        
        Returns:
            JoinResult with matched rows
        """
        if bigdata is None:
            bigdata = self.bigdata
        if smalldata is None:
            smalldata = self.smalldata
            
        print("Performing Hash Lookup (DATA step equivalent)...")
        start_time = time.time()
        
        # Build hash lookup dictionary
        lookup = {
            (row['group'], row['obs']): row['status']
            for _, row in smalldata.iterrows()
        }
        
        # Filter bigdata and add status
        mask = bigdata.apply(
            lambda row: (row['group'], row['obs']) in lookup,
            axis=1
        )
        result_df = bigdata[mask].copy()
        result_df['status'] = result_df.apply(
            lambda row: lookup.get((row['group'], row['obs']), None),
            axis=1
        )
        
        execution_time = time.time() - start_time
        memory_usage = result_df.memory_usage(deep=True).sum()
        
        print(f"Hash Lookup completed in {execution_time:.4f}s, {len(result_df)} rows matched")
        
        return JoinResult(
            data=result_df,
            method="Hash Lookup (DATA step)",
            execution_time=execution_time,
            memory_usage=memory_usage,
            row_count=len(result_df)
        )
    
    def compare_all_methods(self) -> Dict[str, JoinResult]:
        """
        Run all four join methods and compare performance.
        
        Returns:
            Dictionary mapping method name to JoinResult
        """
        if self.bigdata is None or self.smalldata is None:
            raise ValueError("Must create bigdata and smalldata first")
        
        print("\n" + "="*60)
        print("COMPARING ALL JOIN METHODS")
        print("="*60 + "\n")
        
        results = {}
        
        # Run all methods
        results['sequential_loop'] = self.sequential_loop_join()
        print()
        
        results['sort_merge'] = self.sort_merge_join()
        print()
        
        results['hash_join'] = self.hash_join()
        print()
        
        results['hash_lookup'] = self.hash_lookup()
        print()
        
        # Print comparison
        print("="*60)
        print("PERFORMANCE COMPARISON")
        print("="*60)
        print(f"{'Method':<30} {'Time (s)':<12} {'Rows':<10} {'Memory (KB)':<12}")
        print("-"*60)
        
        for name, result in results.items():
            memory_kb = result.memory_usage / 1024
            print(f"{result.method:<30} {result.execution_time:<12.4f} {result.row_count:<10} {memory_kb:<12.2f}")
        
        print("="*60)
        
        return results


def main():
    """
    Main execution function - demonstrates all join strategies.
    """
    # Use smaller dataset for demo (can scale up to 25M)
    n_rows = 1_000_000  # 1M rows for faster demo
    
    magic = SQLMagic(seed=42)
    
    # Create datasets
    bigdata = magic.create_bigdata(n_rows=n_rows)
    smalldata = magic.create_smalldata(bigdata, n_samples=10)
    
    # Compare all methods
    results = magic.compare_all_methods()
    
    # Verify all methods produce same results
    print("\nVERIFYING CONSISTENCY...")
    base_result = results['hash_join'].data.sort_values(['group', 'obs']).reset_index(drop=True)
    
    for name, result in results.items():
        if name == 'hash_join':
            continue
        test_result = result.data.sort_values(['group', 'obs']).reset_index(drop=True)
        
        if len(base_result) == len(test_result) and \
           base_result[['group', 'obs']].equals(test_result[['group', 'obs']]):
            print(f"✓ {result.method}: MATCH")
        else:
            print(f"✗ {result.method}: MISMATCH")


if __name__ == "__main__":
    main()
