"""
Test Harness Generator - Creates comprehensive Excel test harness file
with hierarchical rules, test cases, and automated execution tracking
"""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from typing import List, Dict, Any
import json


class TestHarnessGenerator:
    """Generates Excel-based test harness with hierarchical rules and test cases"""

    def __init__(self):
        self.wb = openpyxl.Workbook()
        # Remove default sheet
        if 'Sheet' in self.wb.sheetnames:
            self.wb.remove(self.wb['Sheet'])

        # Define color scheme
        self.colors = {
            'header': 'FFC000',      # Orange
            'pass': '92D050',        # Green
            'fail': 'FF0000',        # Red
            'pending': 'FFFF00',     # Yellow
            'info': 'D9E1F2',        # Light Blue
            'summary': '4472C4'      # Dark Blue
        }

    def generate_test_harness(self,
                             hierarchical_rules: List[Dict[str, Any]],
                             test_cases: List[Dict[str, Any]],
                             bank_id: str,
                             policy_type: str,
                             output_path: str) -> str:
        """
        Generate comprehensive test harness Excel file

        Args:
            hierarchical_rules: List of hierarchical rules (tree structure)
            test_cases: List of test cases
            bank_id: Bank identifier
            policy_type: Policy type identifier
            output_path: Path to save Excel file

        Returns:
            Path to generated file
        """
        print(f"📊 Generating test harness for {bank_id}/{policy_type}...")

        # Flatten hierarchical rules for easier processing
        flattened_rules = self._flatten_rules(hierarchical_rules)

        # Create sheets
        self._create_hierarchical_rules_sheet(hierarchical_rules, flattened_rules)
        self._create_test_cases_sheet(test_cases)
        self._create_execution_template_sheet(flattened_rules, test_cases)
        self._create_coverage_summary_sheet(flattened_rules, test_cases)
        self._create_instructions_sheet(bank_id, policy_type)

        # Save workbook
        self.wb.save(output_path)
        print(f"✅ Test harness saved to: {output_path}")

        return output_path

    def _flatten_rules(self, rules: List[Dict[str, Any]], parent_id: str = None, level: int = 0) -> List[Dict[str, Any]]:
        """Flatten hierarchical rules tree to list with level information"""
        flattened = []

        for rule in rules:
            rule_copy = {
                'id': rule.get('id', ''),
                'name': rule.get('name', ''),
                'description': rule.get('description', ''),
                'expected': rule.get('expected', ''),
                'actual': rule.get('actual', ''),
                'confidence': rule.get('confidence', 0),
                'passed': rule.get('passed'),
                'page_number': rule.get('page_number'),
                'clause_reference': rule.get('clause_reference', ''),
                'parent_id': parent_id,
                'level': level
            }
            flattened.append(rule_copy)

            # Process dependencies (children)
            if 'dependencies' in rule and rule['dependencies']:
                children = self._flatten_rules(rule['dependencies'], rule['id'], level + 1)
                flattened.extend(children)

        return flattened

    def _create_hierarchical_rules_sheet(self, tree_rules: List[Dict[str, Any]], flattened_rules: List[Dict[str, Any]]):
        """Create Hierarchical Rules sheet with visual indentation"""
        ws = self.wb.create_sheet("Hierarchical Rules", 0)

        # Headers
        headers = ['Rule ID', 'Level', 'Rule Name', 'Description', 'Expected', 'Page', 'Clause', 'Confidence', 'Status']
        self._write_header_row(ws, headers)

        # Data rows
        row = 2
        for rule in flattened_rules:
            indent = "  " * rule['level']  # Indentation based on level

            ws.cell(row, 1, rule['id'])
            ws.cell(row, 2, rule['level'])
            ws.cell(row, 3, f"{indent}{rule['name']}")  # Indented name
            ws.cell(row, 4, rule['description'])
            ws.cell(row, 5, rule['expected'])
            ws.cell(row, 6, rule['page_number'] if rule['page_number'] else 'N/A')
            ws.cell(row, 7, rule['clause_reference'])
            ws.cell(row, 8, rule['confidence'])

            # Status indicator
            status_cell = ws.cell(row, 9, 'Pending')
            status_cell.fill = PatternFill(start_color=self.colors['pending'], fill_type='solid')

            row += 1

        # Adjust column widths
        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 8
        ws.column_dimensions['C'].width = 40
        ws.column_dimensions['D'].width = 50
        ws.column_dimensions['E'].width = 30
        ws.column_dimensions['F'].width = 8
        ws.column_dimensions['G'].width = 25
        ws.column_dimensions['H'].width = 12
        ws.column_dimensions['I'].width = 12

        # Freeze header row
        ws.freeze_panes = 'A2'

    def _create_test_cases_sheet(self, test_cases: List[Dict[str, Any]]):
        """Create Test Cases sheet"""
        ws = self.wb.create_sheet("Test Cases")

        # Headers
        headers = ['Test ID', 'Test Name', 'Category', 'Priority', 'Expected Decision',
                   'Expected Risk', 'Applicant Data', 'Policy Data', 'Expected Reasons']
        self._write_header_row(ws, headers)

        # Data rows
        row = 2
        for idx, tc in enumerate(test_cases, start=1):
            ws.cell(row, 1, f"TC{idx:03d}")
            ws.cell(row, 2, tc.get('test_case_name', ''))
            ws.cell(row, 3, tc.get('category', 'positive'))

            # Priority with color coding
            priority = tc.get('priority', 1)
            priority_cell = ws.cell(row, 4, priority)
            if priority == 1:
                priority_cell.fill = PatternFill(start_color='FF0000', fill_type='solid')
                priority_cell.font = Font(color='FFFFFF', bold=True)
            elif priority == 2:
                priority_cell.fill = PatternFill(start_color='FFC000', fill_type='solid')

            ws.cell(row, 5, tc.get('expected_decision', ''))
            ws.cell(row, 6, tc.get('expected_risk_category', ''))
            ws.cell(row, 7, json.dumps(tc.get('applicant_data', {}), indent=2))
            ws.cell(row, 8, json.dumps(tc.get('policy_data', {}), indent=2))

            reasons = tc.get('expected_reasons', [])
            ws.cell(row, 9, '\n'.join(reasons) if isinstance(reasons, list) else str(reasons))

            row += 1

        # Adjust column widths
        ws.column_dimensions['A'].width = 10
        ws.column_dimensions['B'].width = 35
        ws.column_dimensions['C'].width = 12
        ws.column_dimensions['D'].width = 10
        ws.column_dimensions['E'].width = 15
        ws.column_dimensions['F'].width = 12
        ws.column_dimensions['G'].width = 40
        ws.column_dimensions['H'].width = 40
        ws.column_dimensions['I'].width = 50

        ws.freeze_panes = 'A2'

    def _create_execution_template_sheet(self, flattened_rules: List[Dict[str, Any]], test_cases: List[Dict[str, Any]]):
        """Create Test Execution Template with automated pass/fail formulas"""
        ws = self.wb.create_sheet("Test Execution")

        # Headers
        headers = ['Test ID', 'Rule ID', 'Rule Name', 'Expected', 'Actual Result',
                   'Passed', 'Execution Date', 'Executed By', 'Notes']
        self._write_header_row(ws, headers)

        # Generate rows for each test case x rule combination
        row = 2
        for tc_idx, tc in enumerate(test_cases, start=1):
            test_id = f"TC{tc_idx:03d}"

            for rule in flattened_rules:
                ws.cell(row, 1, test_id)
                ws.cell(row, 2, rule['id'])
                ws.cell(row, 3, rule['name'])
                ws.cell(row, 4, rule['expected'])

                # Actual Result - to be filled during execution
                actual_cell = ws.cell(row, 5, '')
                actual_cell.fill = PatternFill(start_color='FFFF00', fill_type='solid')

                # Passed - Auto-calculated formula
                # Formula: If E (actual) is empty, show "Pending", else compare D (expected) with E (actual)
                passed_cell = ws.cell(row, 6)
                passed_cell.value = f'=IF(E{row}="","Pending",IF(D{row}=E{row},"PASS","FAIL"))'

                # Conditional formatting based on formula result
                # This will be evaluated when the file is opened in Excel

                # Execution Date
                ws.cell(row, 7, '')

                # Executed By
                ws.cell(row, 8, '')

                # Notes
                ws.cell(row, 9, '')

                row += 1

        # Adjust column widths
        ws.column_dimensions['A'].width = 10
        ws.column_dimensions['B'].width = 12
        ws.column_dimensions['C'].width = 35
        ws.column_dimensions['D'].width = 30
        ws.column_dimensions['E'].width = 30
        ws.column_dimensions['F'].width = 10
        ws.column_dimensions['G'].width = 15
        ws.column_dimensions['H'].width = 15
        ws.column_dimensions['I'].width = 40

        ws.freeze_panes = 'A2'

    def _create_coverage_summary_sheet(self, flattened_rules: List[Dict[str, Any]], test_cases: List[Dict[str, Any]]):
        """Create Coverage Summary sheet with statistics and charts"""
        ws = self.wb.create_sheet("Coverage Summary")

        # Title
        title_cell = ws.cell(1, 1, "Test Coverage Summary")
        title_cell.font = Font(size=16, bold=True, color='FFFFFF')
        title_cell.fill = PatternFill(start_color=self.colors['summary'], fill_type='solid')
        ws.merge_cells('A1:B1')

        # Statistics
        row = 3
        stats = [
            ('Total Rules', len(flattened_rules)),
            ('Total Test Cases', len(test_cases)),
            ('Expected Total Test Executions', len(flattened_rules) * len(test_cases)),
            ('', ''),
            ('Rules by Level', ''),
        ]

        # Count rules by level
        level_counts = {}
        for rule in flattened_rules:
            level = rule['level']
            level_counts[level] = level_counts.get(level, 0) + 1

        for level in sorted(level_counts.keys()):
            stats.append((f'  Level {level} Rules', level_counts[level]))

        stats.append(('', ''))
        stats.append(('Test Cases by Category', ''))

        # Count test cases by category
        category_counts = {}
        for tc in test_cases:
            category = tc.get('category', 'positive')
            category_counts[category] = category_counts.get(category, 0) + 1

        for category in sorted(category_counts.keys()):
            stats.append((f'  {category.capitalize()}', category_counts[category]))

        # Write statistics
        for label, value in stats:
            label_cell = ws.cell(row, 1, label)
            if label and not label.startswith('  '):
                label_cell.font = Font(bold=True)

            if value != '':
                ws.cell(row, 2, value)

            row += 1

        # Add execution status summary (will be calculated from Test Execution sheet)
        row += 2
        ws.cell(row, 1, "Execution Status").font = Font(bold=True, size=12)
        row += 1

        # Formula to count PASS/FAIL/Pending from Test Execution sheet
        ws.cell(row, 1, "Total Executed")
        ws.cell(row, 2, f'=COUNTIF(\'Test Execution\'!F:F,"PASS")+COUNTIF(\'Test Execution\'!F:F,"FAIL")')
        row += 1

        ws.cell(row, 1, "Passed")
        pass_cell = ws.cell(row, 2, f'=COUNTIF(\'Test Execution\'!F:F,"PASS")')
        pass_cell.fill = PatternFill(start_color=self.colors['pass'], fill_type='solid')
        row += 1

        ws.cell(row, 1, "Failed")
        fail_cell = ws.cell(row, 2, f'=COUNTIF(\'Test Execution\'!F:F,"FAIL")')
        fail_cell.fill = PatternFill(start_color=self.colors['fail'], fill_type='solid')
        row += 1

        ws.cell(row, 1, "Pending")
        pending_cell = ws.cell(row, 2, f'=COUNTIF(\'Test Execution\'!F:F,"Pending")')
        pending_cell.fill = PatternFill(start_color=self.colors['pending'], fill_type='solid')
        row += 1

        ws.cell(row, 1, "Pass Rate %")
        ws.cell(row, 2, f'=IF(B{row-3}=0,0,ROUND(B{row-2}/B{row-3}*100,2))')

        # Adjust column widths
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 20

    def _create_instructions_sheet(self, bank_id: str, policy_type: str):
        """Create Instructions sheet for test harness users"""
        ws = self.wb.create_sheet("Instructions")

        instructions = f"""
TEST HARNESS INSTRUCTIONS
========================

Bank: {bank_id}
Policy Type: {policy_type}

OVERVIEW
--------
This test harness provides a comprehensive framework for testing underwriting rules with automated
pass/fail validation and coverage tracking.

SHEETS DESCRIPTION
------------------

1. HIERARCHICAL RULES
   - Complete tree of all underwriting rules with visual hierarchy
   - Shows rule IDs, descriptions, expected values, page numbers, and clause references
   - Status column shows overall rule validation status

2. TEST CASES
   - All generated test cases with input data and expected outcomes
   - Categories: positive, negative, boundary, edge_case
   - Priority: 1 (high/critical), 2 (medium), 3 (low)

3. TEST EXECUTION (MAIN WORKING SHEET)
   - Fill in "Actual Result" column (E) during test execution
   - "Passed" column (F) auto-calculates: PASS if Expected = Actual, FAIL otherwise
   - Record execution date, tester name, and notes
   - Color coding: Yellow = Pending, Green = Pass, Red = Fail

4. COVERAGE SUMMARY
   - Real-time statistics and test coverage metrics
   - Auto-updates as you fill in test execution results
   - Shows pass/fail rates and execution progress

HOW TO USE
----------

STEP 1: Review Rules
   - Open "Hierarchical Rules" sheet
   - Understand the rule structure and requirements
   - Note page numbers and clause references for policy lookup

STEP 2: Review Test Cases
   - Open "Test Cases" sheet
   - Understand test scenarios and expected outcomes
   - Focus on high-priority (1) test cases first

STEP 3: Execute Tests
   - Open "Test Execution" sheet
   - For each test case:
     a. Run the test with given input data
     b. Record the actual result in column E
     c. "Passed" column will auto-calculate
     d. Fill in execution date and tester name
     e. Add notes for any issues or observations

STEP 4: Monitor Coverage
   - Check "Coverage Summary" for progress
   - Aim for 100% execution coverage
   - Target > 95% pass rate

TIPS
----
- Start with Priority 1 test cases
- Test positive cases before negative cases
- Document all failures with detailed notes
- Update actual values exactly as shown in system output
- Use formulas - they auto-calculate pass/fail status

AUTOMATION
----------
The "Passed" column uses Excel formulas:
  =IF(E2="","Pending",IF(D2=E2,"PASS","FAIL"))

This automatically compares Expected (D) vs Actual (E) results.

For questions or issues, contact the testing team.
"""

        # Write instructions
        row = 1
        for line in instructions.split('\n'):
            ws.cell(row, 1, line)
            row += 1

        # Format
        ws.column_dimensions['A'].width = 100
        for row in ws.iter_rows(min_row=1, max_row=row):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical='top')

    def _write_header_row(self, ws, headers: List[str]):
        """Write and format header row"""
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(1, col, header)
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color=self.colors['header'], fill_type='solid')
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
