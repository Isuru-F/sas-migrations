"""
Unit tests for SQL Magic migration
Tests core functionality and join correctness
"""

import pytest
import pandas as pd
import numpy as np
from sql_magic import SQLMagic, JoinResult


class TestDataGeneration:
    """Test data generation functions"""
    
    def test_create_bigdata_shape(self):
        """Test bigdata has correct shape and columns"""
        magic = SQLMagic(seed=42)
        n_rows = 1000
        bigdata = magic.create_bigdata(n_rows=n_rows)
        
        assert len(bigdata) == n_rows
        assert list(bigdata.columns) == ['obs', 'group', 'value']
    
    def test_create_bigdata_ranges(self):
        """Test bigdata values are in correct ranges"""
        magic = SQLMagic(seed=42)
        bigdata = magic.create_bigdata(n_rows=1000)
        
        assert bigdata['obs'].min() >= 1
        assert bigdata['obs'].max() <= 1_000_000_000
        assert bigdata['group'].min() >= 1
        assert bigdata['group'].max() <= 5
        assert bigdata['value'].min() >= 0.0
        assert bigdata['value'].max() <= 1.0
    
    def test_create_bigdata_reproducibility(self):
        """Test that same seed produces same data"""
        magic1 = SQLMagic(seed=42)
        bigdata1 = magic1.create_bigdata(n_rows=100)
        
        magic2 = SQLMagic(seed=42)
        bigdata2 = magic2.create_bigdata(n_rows=100)
        
        pd.testing.assert_frame_equal(bigdata1, bigdata2)
    
    def test_create_smalldata_shape(self):
        """Test smalldata has correct shape and columns"""
        magic = SQLMagic(seed=42)
        bigdata = magic.create_bigdata(n_rows=1000)
        smalldata = magic.create_smalldata(bigdata, n_samples=10)
        
        assert len(smalldata) == 10
        assert list(smalldata.columns) == ['obs', 'group', 'status']
    
    def test_create_smalldata_status(self):
        """Test smalldata has correct status values"""
        magic = SQLMagic(seed=42)
        bigdata = magic.create_bigdata(n_rows=1000)
        smalldata = magic.create_smalldata(bigdata, n_samples=10)
        
        assert all(smalldata['status'] == 'Found it!')
    
    def test_create_smalldata_samples_from_bigdata(self):
        """Test that smalldata values exist in bigdata"""
        magic = SQLMagic(seed=42)
        bigdata = magic.create_bigdata(n_rows=1000)
        smalldata = magic.create_smalldata(bigdata, n_samples=10)
        
        # Check that all smalldata (group, obs) pairs exist in bigdata
        for _, row in smalldata.iterrows():
            match = bigdata[
                (bigdata['group'] == row['group']) & 
                (bigdata['obs'] == row['obs'])
            ]
            assert len(match) > 0


class TestJoinMethods:
    """Test join method implementations"""
    
    @pytest.fixture
    def magic_with_data(self):
        """Fixture providing SQLMagic with small test datasets"""
        magic = SQLMagic(seed=42)
        
        # Create small test datasets
        magic.bigdata = pd.DataFrame({
            'obs': [100, 200, 300, 400, 500],
            'group': [1, 2, 1, 3, 2],
            'value': [0.1, 0.2, 0.3, 0.4, 0.5]
        })
        
        magic.smalldata = pd.DataFrame({
            'obs': [100, 300],
            'group': [1, 1],
            'status': ['Found it!', 'Found it!']
        })
        
        return magic
    
    def test_sequential_loop_join(self, magic_with_data):
        """Test sequential loop join produces correct results"""
        result = magic_with_data.sequential_loop_join()
        
        assert isinstance(result, JoinResult)
        assert result.row_count == 2
        assert 'status' in result.data.columns
        assert all(result.data['status'] == 'Found it!')
        
        # Check specific matches
        expected_obs = {100, 300}
        assert set(result.data['obs']) == expected_obs
    
    def test_sort_merge_join(self, magic_with_data):
        """Test sort merge join produces correct results"""
        result = magic_with_data.sort_merge_join()
        
        assert isinstance(result, JoinResult)
        assert result.row_count == 2
        assert 'status' in result.data.columns
        
        expected_obs = {100, 300}
        assert set(result.data['obs']) == expected_obs
    
    def test_hash_join(self, magic_with_data):
        """Test hash join produces correct results"""
        result = magic_with_data.hash_join()
        
        assert isinstance(result, JoinResult)
        assert result.row_count == 2
        assert 'status' in result.data.columns
        
        expected_obs = {100, 300}
        assert set(result.data['obs']) == expected_obs
    
    def test_hash_lookup(self, magic_with_data):
        """Test hash lookup produces correct results"""
        result = magic_with_data.hash_lookup()
        
        assert isinstance(result, JoinResult)
        assert result.row_count == 2
        assert 'status' in result.data.columns
        
        expected_obs = {100, 300}
        assert set(result.data['obs']) == expected_obs
    
    def test_all_methods_produce_same_results(self, magic_with_data):
        """Test that all join methods produce identical results"""
        seq_result = magic_with_data.sequential_loop_join()
        merge_result = magic_with_data.sort_merge_join()
        hash_result = magic_with_data.hash_join()
        lookup_result = magic_with_data.hash_lookup()
        
        # Sort all results for comparison
        seq_sorted = seq_result.data.sort_values(['group', 'obs']).reset_index(drop=True)
        merge_sorted = merge_result.data.sort_values(['group', 'obs']).reset_index(drop=True)
        hash_sorted = hash_result.data.sort_values(['group', 'obs']).reset_index(drop=True)
        lookup_sorted = lookup_result.data.sort_values(['group', 'obs']).reset_index(drop=True)
        
        # Compare row counts
        assert seq_result.row_count == merge_result.row_count
        assert seq_result.row_count == hash_result.row_count
        assert seq_result.row_count == lookup_result.row_count
        
        # Compare actual data
        pd.testing.assert_frame_equal(
            seq_sorted[['group', 'obs', 'status']], 
            merge_sorted[['group', 'obs', 'status']]
        )
        pd.testing.assert_frame_equal(
            seq_sorted[['group', 'obs', 'status']], 
            hash_sorted[['group', 'obs', 'status']]
        )
        pd.testing.assert_frame_equal(
            seq_sorted[['group', 'obs', 'status']], 
            lookup_sorted[['group', 'obs', 'status']]
        )


class TestJoinResult:
    """Test JoinResult dataclass"""
    
    def test_join_result_attributes(self):
        """Test JoinResult has correct attributes"""
        df = pd.DataFrame({'a': [1, 2, 3]})
        result = JoinResult(
            data=df,
            method="Test Method",
            execution_time=1.5,
            memory_usage=1024,
            row_count=3
        )
        
        assert result.method == "Test Method"
        assert result.execution_time == 1.5
        assert result.memory_usage == 1024
        assert result.row_count == 3
        assert len(result.data) == 3


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_no_matches(self):
        """Test when there are no matching rows"""
        magic = SQLMagic(seed=42)
        
        magic.bigdata = pd.DataFrame({
            'obs': [100, 200, 300],
            'group': [1, 2, 3],
            'value': [0.1, 0.2, 0.3]
        })
        
        magic.smalldata = pd.DataFrame({
            'obs': [999],  # No match
            'group': [9],
            'status': ['Found it!']
        })
        
        result = magic.hash_join()
        assert result.row_count == 0
        assert len(result.data) == 0
    
    def test_multiple_matches(self):
        """Test when one smalldata row matches multiple bigdata rows"""
        magic = SQLMagic(seed=42)
        
        magic.bigdata = pd.DataFrame({
            'obs': [100, 100, 200],
            'group': [1, 1, 2],
            'value': [0.1, 0.2, 0.3]
        })
        
        magic.smalldata = pd.DataFrame({
            'obs': [100],
            'group': [1],
            'status': ['Found it!']
        })
        
        result = magic.hash_join()
        assert result.row_count == 2
    
    def test_create_smalldata_without_bigdata(self):
        """Test that creating smalldata without bigdata raises error"""
        magic = SQLMagic(seed=42)
        
        with pytest.raises(ValueError, match="bigdata must be created"):
            magic.create_smalldata()
    
    def test_join_without_data(self):
        """Test that joining without data raises error"""
        magic = SQLMagic(seed=42)
        
        with pytest.raises(ValueError):
            magic.compare_all_methods()


class TestPerformance:
    """Test performance characteristics"""
    
    def test_hash_join_faster_than_loop(self):
        """Test that hash join is faster than sequential loop on moderate data"""
        magic = SQLMagic(seed=42)
        magic.create_bigdata(n_rows=10_000)
        magic.create_smalldata(n_samples=10)
        
        loop_result = magic.sequential_loop_join()
        hash_result = magic.hash_join()
        
        # Hash join should be faster (allowing some variance)
        assert hash_result.execution_time <= loop_result.execution_time * 2
    
    def test_all_methods_return_timing(self):
        """Test that all methods return execution time"""
        magic = SQLMagic(seed=42)
        magic.create_bigdata(n_rows=1000)
        magic.create_smalldata(n_samples=5)
        
        results = [
            magic.sequential_loop_join(),
            magic.sort_merge_join(),
            magic.hash_join(),
            magic.hash_lookup()
        ]
        
        for result in results:
            assert result.execution_time > 0
            assert result.memory_usage > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
