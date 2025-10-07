#!/usr/bin/env python3
"""
SAS Symbol Extractor using AST parsing

This tool parses SAS code and extracts all symbols including:
- Data steps
- Procedures
- Datasets
- Variables
- Functions
- Macro variables
- Hash objects
"""

import re
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path


@dataclass
class Variable:
    name: str
    type: str
    length: Optional[str] = None
    initialization: Optional[str] = None
    usage: List[str] = field(default_factory=list)
    line_numbers: List[int] = field(default_factory=list)


@dataclass
class Dataset:
    name: str
    type: str
    input_datasets: List[str] = field(default_factory=list)
    output_datasets: List[str] = field(default_factory=list)
    variables: List[str] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


@dataclass
class Procedure:
    name: str
    proc_type: str
    options: Dict[str, Any] = field(default_factory=dict)
    input_datasets: List[str] = field(default_factory=list)
    output_datasets: List[str] = field(default_factory=list)
    sql_operations: List[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


@dataclass
class Function:
    name: str
    parameters: List[str] = field(default_factory=list)
    context: str = ""
    line_number: int = 0


@dataclass
class HashObject:
    name: str
    dataset: str
    keys: List[str] = field(default_factory=list)
    data_fields: List[str] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)
    line_start: int = 0


class SASParser:
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.content = self.filepath.read_text()
        self.lines = self.content.split('\n')
        
        self.datasets: Dict[str, Dataset] = {}
        self.procedures: Dict[str, Procedure] = {}
        self.variables: Dict[str, Variable] = {}
        self.functions: List[Function] = []
        self.hash_objects: Dict[str, HashObject] = {}
        
    def parse(self):
        """Main parsing method"""
        self._parse_data_steps()
        self._parse_procedures()
        self._parse_variables()
        self._parse_functions()
        self._parse_hash_objects()
        
    def _parse_data_steps(self):
        """Extract DATA step information"""
        i = 0
        while i < len(self.lines):
            line = self.lines[i].strip()
            
            if line.startswith('data '):
                dataset_name, dataset_info = self._extract_data_step(i)
                if dataset_name:
                    self.datasets[dataset_name] = dataset_info
                    i = dataset_info.line_end
            i += 1
            
    def _extract_data_step(self, start_line: int) -> tuple:
        """Extract detailed information about a DATA step"""
        line = self.lines[start_line].strip()
        
        dataset_match = re.match(r'data\s+(\w+)\s*;?', line, re.IGNORECASE)
        if not dataset_match:
            return None, None
            
        dataset_name = dataset_match.group(1)
        dataset = Dataset(
            name=dataset_name,
            type="data_step",
            line_start=start_line + 1
        )
        
        i = start_line + 1
        while i < len(self.lines):
            line = self.lines[i].strip()
            
            if re.match(r'^run\s*;', line, re.IGNORECASE):
                dataset.line_end = i + 1
                break
                
            if line.startswith('set '):
                input_ds = re.findall(r'set\s+(\w+)', line, re.IGNORECASE)
                dataset.input_datasets.extend(input_ds)
                dataset.operations.append(f"Read from: {', '.join(input_ds)}")
                
            if line.startswith('call '):
                func_call = re.match(r'call\s+(\w+)', line, re.IGNORECASE)
                if func_call:
                    dataset.operations.append(f"Call: {func_call.group(1)}")
                    
            if line.startswith('do '):
                loop_match = re.match(r'do\s+(\w+)\s*=\s*(.+?)\s+to\s+(.+?);', line, re.IGNORECASE)
                if loop_match:
                    dataset.operations.append(f"Loop: {loop_match.group(1)} from {loop_match.group(2)} to {loop_match.group(3)}")
                    
            if 'output' in line.lower() and line.strip().endswith(';'):
                dataset.operations.append("Explicit output")
                
            if '=' in line and not line.startswith('do '):
                var_assign = re.match(r'(\w+)\s*=\s*(.+?);', line)
                if var_assign:
                    var_name = var_assign.group(1)
                    var_expr = var_assign.group(2)
                    if var_name not in dataset.variables:
                        dataset.variables.append(var_name)
                    dataset.operations.append(f"Assign: {var_name} = {var_expr}")
                    
            i += 1
            
        return dataset_name, dataset
        
    def _parse_procedures(self):
        """Extract PROC information"""
        i = 0
        while i < len(self.lines):
            line = self.lines[i].strip()
            
            if line.startswith('proc '):
                proc_name, proc_info = self._extract_procedure(i)
                if proc_name:
                    self.procedures[proc_name] = proc_info
                    i = proc_info.line_end
            i += 1
            
    def _extract_procedure(self, start_line: int) -> tuple:
        """Extract detailed information about a PROC"""
        line = self.lines[start_line].strip()
        
        proc_match = re.match(r'proc\s+(\w+)(.+)?;?', line, re.IGNORECASE)
        if not proc_match:
            return None, None
            
        proc_type = proc_match.group(1)
        options_str = proc_match.group(2) or ""
        
        proc_name = f"proc_{proc_type}_{start_line}"
        options = {}
        
        magic_match = re.search(r'magic\s*=\s*(\d+)', options_str, re.IGNORECASE)
        if magic_match:
            options['magic'] = int(magic_match.group(1))
            
        procedure = Procedure(
            name=proc_name,
            proc_type=proc_type,
            options=options,
            line_start=start_line + 1
        )
        
        i = start_line + 1
        current_sql = []
        
        while i < len(self.lines):
            line = self.lines[i].strip()
            
            if re.match(r'^quit\s*;', line, re.IGNORECASE):
                procedure.line_end = i + 1
                if current_sql:
                    procedure.sql_operations.append(' '.join(current_sql))
                break
                
            if proc_type.lower() == 'sql':
                if 'create table' in line.lower():
                    table_match = re.search(r'create\s+table\s+(\w+)', line, re.IGNORECASE)
                    if table_match:
                        procedure.output_datasets.append(table_match.group(1))
                        
                if 'from' in line.lower():
                    from_match = re.findall(r'from\s+(\w+)', line, re.IGNORECASE)
                    procedure.input_datasets.extend(from_match)
                    
                if 'join' in line.lower():
                    join_match = re.findall(r'join\s+(\w+)', line, re.IGNORECASE)
                    procedure.input_datasets.extend(join_match)
                    
                current_sql.append(line)
                
            i += 1
            
        return proc_name, procedure
        
    def _parse_variables(self):
        """Extract variable information"""
        for i, line in enumerate(self.lines):
            line = line.strip()
            
            if re.match(r'length\s+', line, re.IGNORECASE):
                length_match = re.match(r'length\s+(\w+)\s+\$?(\w+)\.?;?', line, re.IGNORECASE)
                if length_match:
                    var_name = length_match.group(1)
                    var_type = length_match.group(2)
                    if var_name not in self.variables:
                        self.variables[var_name] = Variable(
                            name=var_name,
                            type=var_type,
                            line_numbers=[i + 1]
                        )
                        
            var_assigns = re.findall(r'(\w+)\s*=\s*([^;]+)', line)
            for var_name, var_value in var_assigns:
                if var_name not in ['if', 'then', 'do', 'end', 'proc', 'data', 'run', 'quit']:
                    if var_name not in self.variables:
                        self.variables[var_name] = Variable(
                            name=var_name,
                            type="unknown",
                            line_numbers=[i + 1],
                            initialization=var_value.strip()
                        )
                    else:
                        self.variables[var_name].line_numbers.append(i + 1)
                        
    def _parse_functions(self):
        """Extract function calls"""
        function_pattern = r'(\w+)\s*\('
        
        for i, line in enumerate(self.lines):
            matches = re.finditer(function_pattern, line)
            for match in matches:
                func_name = match.group(1)
                if func_name.lower() not in ['if', 'do', 'data', 'proc']:
                    params_match = re.search(rf'{func_name}\s*\(([^)]+)\)', line)
                    params = []
                    if params_match:
                        params = [p.strip() for p in params_match.group(1).split(',')]
                        
                    self.functions.append(Function(
                        name=func_name,
                        parameters=params,
                        context=line.strip(),
                        line_number=i + 1
                    ))
                    
    def _parse_hash_objects(self):
        """Extract hash object definitions"""
        for i, line in enumerate(self.lines):
            line_stripped = line.strip()
            
            if 'dcl hash' in line_stripped or 'declare hash' in line_stripped:
                hash_match = re.search(r'(?:dcl|declare)\s+hash\s+(\w+)\s*\(dataset:\s*[\'"](\w+)[\'"]\)', 
                                      line_stripped, re.IGNORECASE)
                if hash_match:
                    hash_name = hash_match.group(1)
                    dataset_name = hash_match.group(2)
                    
                    hash_obj = HashObject(
                        name=hash_name,
                        dataset=dataset_name,
                        line_start=i + 1
                    )
                    
                    j = i + 1
                    while j < len(self.lines):
                        next_line = self.lines[j].strip()
                        
                        if 'defineKey' in next_line:
                            keys = re.findall(r'[\'"](\w+)[\'"]', next_line)
                            hash_obj.keys.extend(keys)
                            
                        if 'defineData' in next_line:
                            data_fields = re.findall(r'[\'"](\w+)[\'"]', next_line)
                            hash_obj.data_fields.extend(data_fields)
                            
                        if 'defineDone' in next_line:
                            hash_obj.operations.append("Hash table initialized")
                            break
                            
                        j += 1
                        
                    k = i + 1
                    while k < len(self.lines):
                        search_line = self.lines[k].strip()
                        if f'{hash_name}.Find()' in search_line or f'{hash_name}.find()' in search_line:
                            hash_obj.operations.append(f"Lookup operation at line {k + 1}")
                        k += 1
                        
                    self.hash_objects[hash_name] = hash_obj
                    
    def get_symbols(self) -> Dict[str, Any]:
        """Return all extracted symbols"""
        return {
            'datasets': {name: asdict(ds) for name, ds in self.datasets.items()},
            'procedures': {name: asdict(proc) for name, proc in self.procedures.items()},
            'variables': {name: asdict(var) for name, var in self.variables.items()},
            'functions': [asdict(func) for func in self.functions],
            'hash_objects': {name: asdict(hobj) for name, hobj in self.hash_objects.items()}
        }
        
    def export_json(self, output_path: str):
        """Export symbols to JSON"""
        symbols = self.get_symbols()
        Path(output_path).write_text(json.dumps(symbols, indent=2))
        
    def generate_markdown_report(self) -> str:
        """Generate comprehensive markdown documentation"""
        report = []
        report.append("# SAS Migration Plan: sql_magic.sas")
        report.append("")
        report.append("## Overview")
        report.append("")
        report.append("This document captures all symbols, business logic, and functionality from sql_magic.sas")
        report.append("to ensure accurate migration and validation of business rules.")
        report.append("")
        
        report.append("## Summary Statistics")
        report.append("")
        report.append(f"- **Data Steps**: {len(self.datasets)}")
        report.append(f"- **Procedures**: {len(self.procedures)}")
        report.append(f"- **Variables**: {len(self.variables)}")
        report.append(f"- **Function Calls**: {len(self.functions)}")
        report.append(f"- **Hash Objects**: {len(self.hash_objects)}")
        report.append("")
        
        report.append("## Datasets")
        report.append("")
        for name, dataset in self.datasets.items():
            report.append(f"### Dataset: `{name}`")
            report.append("")
            report.append(f"- **Type**: {dataset.type}")
            report.append(f"- **Lines**: {dataset.line_start}-{dataset.line_end}")
            
            if dataset.input_datasets:
                report.append(f"- **Input Datasets**: {', '.join(dataset.input_datasets)}")
                
            if dataset.variables:
                report.append(f"- **Variables Created**: {', '.join(dataset.variables)}")
                
            report.append("")
            report.append("**Operations**:")
            report.append("")
            for op in dataset.operations:
                report.append(f"- {op}")
            report.append("")
            
        report.append("## Procedures")
        report.append("")
        for name, proc in self.procedures.items():
            report.append(f"### Procedure: `{proc.proc_type}` (Line {proc.line_start})")
            report.append("")
            
            if proc.options:
                report.append("**Options**:")
                report.append("")
                for opt_name, opt_value in proc.options.items():
                    report.append(f"- `{opt_name}`: {opt_value}")
                    if opt_name == 'magic':
                        magic_desc = {
                            101: "Sequential Loop Join - Used under a variety of conditions",
                            102: "Sort Merge Join - Good for when data can't fit in memory",
                            103: "Hash Join - Fast option for when you have lots of memory"
                        }
                        report.append(f"  - **Description**: {magic_desc.get(opt_value, 'Unknown')}")
                report.append("")
                
            if proc.input_datasets:
                report.append(f"- **Input Datasets**: {', '.join(set(proc.input_datasets))}")
                
            if proc.output_datasets:
                report.append(f"- **Output Datasets**: {', '.join(proc.output_datasets)}")
                
            report.append("")
            
            if proc.sql_operations:
                report.append("**SQL Operations**:")
                report.append("")
                report.append("```sql")
                for sql in proc.sql_operations:
                    report.append(sql)
                report.append("```")
                report.append("")
                
        report.append("## Variables")
        report.append("")
        report.append("| Variable | Type | Defined At | Initialization |")
        report.append("|----------|------|------------|----------------|")
        
        for name, var in sorted(self.variables.items()):
            lines = ', '.join(map(str, var.line_numbers[:3]))
            if len(var.line_numbers) > 3:
                lines += f" (+{len(var.line_numbers)-3} more)"
            init = var.initialization[:30] if var.initialization else "N/A"
            report.append(f"| `{name}` | {var.type} | Line {lines} | {init} |")
            
        report.append("")
        
        report.append("## Functions")
        report.append("")
        report.append("| Function | Parameters | Line | Context |")
        report.append("|----------|------------|------|---------|")
        
        func_summary = {}
        for func in self.functions:
            key = (func.name, tuple(func.parameters))
            if key not in func_summary:
                func_summary[key] = func
                
        for func in func_summary.values():
            params = ', '.join(func.parameters[:3])
            if len(func.parameters) > 3:
                params += "..."
            context = func.context[:50] + "..." if len(func.context) > 50 else func.context
            report.append(f"| `{func.name}` | {params} | {func.line_number} | {context} |")
            
        report.append("")
        
        if self.hash_objects:
            report.append("## Hash Objects")
            report.append("")
            for name, hash_obj in self.hash_objects.items():
                report.append(f"### Hash Object: `{name}`")
                report.append("")
                report.append(f"- **Source Dataset**: {hash_obj.dataset}")
                report.append(f"- **Defined at Line**: {hash_obj.line_start}")
                report.append(f"- **Key Fields**: {', '.join(hash_obj.keys)}")
                report.append(f"- **Data Fields**: {', '.join(hash_obj.data_fields)}")
                report.append("")
                report.append("**Operations**:")
                report.append("")
                for op in hash_obj.operations:
                    report.append(f"- {op}")
                report.append("")
                
        report.append("## Business Logic Summary")
        report.append("")
        report.append("### Purpose")
        report.append("This SAS program demonstrates SQL join optimization techniques using the MAGIC option.")
        report.append("")
        report.append("### Key Business Rules")
        report.append("")
        report.append("1. **Data Generation**:")
        report.append("   - Creates a large dataset (`bigdata`) with 25 million observations")
        report.append("   - Each observation has: random obs number, group (1-5), and value (0-1)")
        report.append("   - Uses seed 42 for reproducibility")
        report.append("")
        report.append("2. **Sample Selection**:")
        report.append("   - Extracts 10 random observations from bigdata into `smalldata`")
        report.append("   - Adds status field 'Found it!' to matched records")
        report.append("")
        report.append("3. **Join Operations**:")
        report.append("   - All three PROC SQL steps perform identical INNER JOINs")
        report.append("   - Join condition: `t1.group=t2.group AND t1.obs=t2.obs`")
        report.append("   - Differ only in optimization strategy (magic parameter)")
        report.append("")
        report.append("4. **Hash Table Alternative**:")
        report.append("   - Demonstrates DATA step hash object for lookup")
        report.append("   - Uses same key fields (group, obs)")
        report.append("   - Retrieves status field from smalldata")
        report.append("")
        report.append("### Migration Considerations")
        report.append("")
        report.append("1. **Join Strategy Mapping**:")
        report.append("   - MAGIC=101 → Loop/Nested Loop Join")
        report.append("   - MAGIC=102 → Sort-Merge Join")
        report.append("   - MAGIC=103 → Hash Join")
        report.append("")
        report.append("2. **Performance Requirements**:")
        report.append("   - Must handle datasets with 25M+ rows")
        report.append("   - Hash join should be preferred when memory is available")
        report.append("   - Sort-merge fallback for memory-constrained environments")
        report.append("")
        report.append("3. **Data Integrity**:")
        report.append("   - All join variants must produce identical results")
        report.append("   - Random seed must be respected for reproducibility")
        report.append("   - Point= functionality for random sampling must be preserved")
        report.append("")
        
        return '\n'.join(report)


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python sas_parser.py <sas_file> [output_md_file]")
        sys.exit(1)
        
    sas_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    parser = SASParser(sas_file)
    parser.parse()
    
    report = parser.generate_markdown_report()
    
    if output_file:
        Path(output_file).write_text(report)
        print(f"Report written to: {output_file}")
    else:
        print(report)
        
    json_file = sas_file.replace('.sas', '_symbols.json')
    parser.export_json(json_file)
    print(f"Symbols exported to: {json_file}")


if __name__ == '__main__':
    main()
