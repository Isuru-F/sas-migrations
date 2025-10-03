#!/usr/bin/env python3
"""
SAS Language Parser using ANTLR4
Extracts symbols, variables, procedures, and business logic from SAS files
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Set


@dataclass
class Variable:
    name: str
    type: str
    context: str
    line_number: int
    description: str = ""


@dataclass
class Procedure:
    name: str
    type: str
    options: List[str]
    input_datasets: List[str]
    output_datasets: List[str]
    line_start: int
    line_end: int
    sql_query: str = ""
    description: str = ""


@dataclass
class DataStep:
    name: str
    input_datasets: List[str]
    output_dataset: str
    variables_created: List[str]
    operations: List[str]
    line_start: int
    line_end: int
    description: str = ""


@dataclass
class SymbolTable:
    variables: List[Variable]
    procedures: List[Procedure]
    data_steps: List[DataStep]
    datasets: Set[str]
    comments: List[Dict[str, Any]]


class SASParser:
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.lines = []
        self.symbol_table = SymbolTable(
            variables=[],
            procedures=[],
            data_steps=[],
            datasets=set(),
            comments=[]
        )
        
    def parse(self) -> SymbolTable:
        """Parse the SAS file and extract all symbols"""
        with open(self.filepath, 'r') as f:
            self.lines = f.readlines()
        
        self._extract_comments()
        self._extract_data_steps()
        self._extract_proc_sql()
        self._extract_datasets()
        
        return self.symbol_table
    
    def _extract_comments(self):
        """Extract all comments and their locations"""
        in_block_comment = False
        block_start = 0
        block_lines = []
        
        for i, line in enumerate(self.lines, 1):
            stripped = line.strip()
            
            # Block comments
            if '/*' in line:
                in_block_comment = True
                block_start = i
                block_lines = [line]
            elif '*/' in line and in_block_comment:
                block_lines.append(line)
                comment_text = ''.join(block_lines)
                self.symbol_table.comments.append({
                    'type': 'block',
                    'text': comment_text,
                    'line_start': block_start,
                    'line_end': i
                })
                in_block_comment = False
                block_lines = []
            elif in_block_comment:
                block_lines.append(line)
    
    def _extract_data_steps(self):
        """Extract DATA steps and their components"""
        i = 0
        while i < len(self.lines):
            line = self.lines[i].strip()
            
            # Match DATA step
            data_match = re.match(r'data\s+(\w+)\s*;', line, re.IGNORECASE)
            if data_match:
                data_step = self._parse_data_step(i, data_match.group(1))
                if data_step:
                    self.symbol_table.data_steps.append(data_step)
                    i = data_step.line_end
                    continue
            i += 1
    
    def _parse_data_step(self, start_line: int, output_name: str) -> DataStep:
        """Parse a single DATA step"""
        input_datasets = []
        variables_created = []
        operations = []
        
        i = start_line
        while i < len(self.lines):
            line = self.lines[i].strip()
            
            # End of DATA step
            if re.match(r'run\s*;', line, re.IGNORECASE):
                return DataStep(
                    name=output_name,
                    input_datasets=input_datasets,
                    output_dataset=output_name,
                    variables_created=variables_created,
                    operations=operations,
                    line_start=start_line + 1,
                    line_end=i + 1
                )
            
            # SET statement
            set_match = re.search(r'set\s+(\w+)', line, re.IGNORECASE)
            if set_match:
                input_datasets.append(set_match.group(1))
            
            # Variable assignments
            assign_match = re.match(r'(\w+)\s*=', line)
            if assign_match and not line.startswith('if') and not line.startswith('do'):
                var_name = assign_match.group(1)
                variables_created.append(var_name)
                
                # Detect variable type and purpose
                if 'rand(' in line:
                    operations.append(f"Random generation: {var_name}")
                elif 'call streaminit' in line:
                    operations.append("Initialize random seed")
            
            # DO loops
            if re.match(r'do\s+', line, re.IGNORECASE):
                operations.append(f"Loop: {line}")
            
            # Hash table operations
            if 'dcl hash' in line.lower():
                operations.append("Hash table declaration")
            if 'defineKey' in line or 'defineData' in line:
                operations.append(f"Hash definition: {line}")
            
            # OUTPUT statement
            if re.match(r'output\s*;', line, re.IGNORECASE):
                operations.append("Output observation")
            
            # CALL statements
            if re.match(r'call\s+', line, re.IGNORECASE):
                operations.append(f"Function call: {line}")
            
            i += 1
        
        return None
    
    def _extract_proc_sql(self):
        """Extract PROC SQL procedures"""
        i = 0
        while i < len(self.lines):
            line = self.lines[i].strip()
            
            # Match PROC SQL with options
            proc_match = re.match(r'proc\s+sql\s*(.*?)\s*;', line, re.IGNORECASE)
            if proc_match:
                options_str = proc_match.group(1)
                options = [opt.strip() for opt in options_str.split() if opt.strip()]
                
                proc = self._parse_proc_sql(i, options)
                if proc:
                    self.symbol_table.procedures.append(proc)
                    i = proc.line_end
                    continue
            i += 1
    
    def _parse_proc_sql(self, start_line: int, options: List[str]) -> Procedure:
        """Parse a PROC SQL block"""
        i = start_line + 1
        sql_lines = []
        output_table = ""
        input_tables = []
        
        while i < len(self.lines):
            line = self.lines[i].strip()
            
            # End of PROC SQL
            if re.match(r'quit\s*;', line, re.IGNORECASE):
                sql_query = ' '.join(sql_lines)
                
                return Procedure(
                    name="PROC SQL",
                    type="sql",
                    options=options,
                    input_datasets=input_tables,
                    output_datasets=[output_table] if output_table else [],
                    line_start=start_line + 1,
                    line_end=i + 1,
                    sql_query=sql_query
                )
            
            sql_lines.append(line)
            
            # CREATE TABLE
            create_match = re.search(r'create\s+table\s+(\w+)', line, re.IGNORECASE)
            if create_match:
                output_table = create_match.group(1)
            
            # FROM clause
            from_match = re.search(r'from\s+(\w+)', line, re.IGNORECASE)
            if from_match:
                input_tables.append(from_match.group(1))
            
            # JOIN clause
            join_match = re.search(r'join\s+(\w+)', line, re.IGNORECASE)
            if join_match:
                input_tables.append(join_match.group(1))
            
            i += 1
        
        return None
    
    def _extract_datasets(self):
        """Compile all unique datasets referenced"""
        for data_step in self.symbol_table.data_steps:
            self.symbol_table.datasets.add(data_step.output_dataset)
            self.symbol_table.datasets.update(data_step.input_datasets)
        
        for proc in self.symbol_table.procedures:
            self.symbol_table.datasets.update(proc.input_datasets)
            self.symbol_table.datasets.update(proc.output_datasets)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert symbol table to dictionary"""
        return {
            'filepath': str(self.filepath),
            'variables': [asdict(v) for v in self.symbol_table.variables],
            'procedures': [asdict(p) for p in self.symbol_table.procedures],
            'data_steps': [asdict(d) for d in self.symbol_table.data_steps],
            'datasets': sorted(list(self.symbol_table.datasets)),
            'comments': self.symbol_table.comments
        }
    
    def to_json(self, output_path: str = None) -> str:
        """Export symbol table as JSON"""
        data = self.to_dict()
        json_str = json.dumps(data, indent=2)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(json_str)
        
        return json_str


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python sas_parser.py <sas_file>")
        sys.exit(1)
    
    parser = SASParser(sys.argv[1])
    symbol_table = parser.parse()
    
    # Output to JSON
    output_file = sys.argv[2] if len(sys.argv) > 2 else "symbols.json"
    parser.to_json(output_file)
    print(f"Symbols extracted to {output_file}")


if __name__ == "__main__":
    main()
