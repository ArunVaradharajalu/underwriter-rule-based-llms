"""
Test Executor - Executes test cases against deployed Drools rules
"""

import json
import logging
import requests
import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class TestExecutor:
    """Executes test cases against Drools KIE Server and records results"""

    def __init__(self, db_service, drools_service=None, field_mapper=None):
        """
        Initialize test executor

        Args:
            db_service: DatabaseService instance for storing execution results
            drools_service: DroolsService instance for executing rules
            field_mapper: IntelligentFieldMapper instance for dynamic field mapping
        """
        self.db_service = db_service
        self.drools_service = drools_service
        self.field_mapper = field_mapper  # Dynamic field mapper

    def execute_all_tests(self,
                         bank_id: str,
                         policy_type: str,
                         container_id: str) -> Dict[str, Any]:
        """
        Execute all test cases for a given bank/policy type combination

        Args:
            bank_id: Bank identifier
            policy_type: Policy type identifier
            container_id: Drools container ID to execute against

        Returns:
            Dictionary with execution summary and results
        """
        print(f"\n{'='*60}")
        print(f"Executing all test cases for {bank_id}/{policy_type}")
        print(f"Using container: {container_id}")
        print(f"{'='*60}")

        # Get all test cases from database (model objects, not dicts)
        test_cases = self.db_service.get_test_cases_raw(bank_id, policy_type)

        if not test_cases:
            print("⚠ No test cases found in database")
            return {
                "status": "warning",
                "message": "No test cases found",
                "total_cases": 0,
                "executed": 0,
                "passed": 0,
                "failed": 0
            }

        print(f"✓ Found {len(test_cases)} test cases to execute")

        # Execute each test case
        results = []
        passed_count = 0
        failed_count = 0
        error_count = 0

        for idx, test_case in enumerate(test_cases, 1):
            print(f"\n[{idx}/{len(test_cases)}] Executing: {test_case.test_case_name}")

            try:
                execution_result = self._execute_single_test(
                    test_case=test_case,
                    container_id=container_id
                )

                results.append(execution_result)

                if execution_result.get('test_passed'):
                    passed_count += 1
                    print(f"  ✓ PASSED")
                else:
                    failed_count += 1
                    print(f"  ✗ FAILED: {execution_result.get('fail_reason', 'Unknown reason')}")

            except Exception as e:
                error_count += 1
                print(f"  ⚠ ERROR: {str(e)}")
                results.append({
                    "test_case_id": test_case.id,
                    "test_case_name": test_case.test_case_name,
                    "status": "error",
                    "error": str(e)
                })

        # Summary
        print(f"\n{'='*60}")
        print(f"Test Execution Summary")
        print(f"{'='*60}")
        print(f"Total test cases: {len(test_cases)}")
        print(f"✓ Passed: {passed_count}")
        print(f"✗ Failed: {failed_count}")
        print(f"⚠ Errors: {error_count}")
        print(f"Pass rate: {(passed_count / len(test_cases) * 100):.1f}%")
        print(f"{'='*60}")

        return {
            "status": "success",
            "total_cases": len(test_cases),
            "executed": passed_count + failed_count,
            "passed": passed_count,
            "failed": failed_count,
            "errors": error_count,
            "pass_rate": (passed_count / len(test_cases) * 100) if test_cases else 0,
            "results": results
        }

    def _execute_single_test(self,
                            test_case,
                            container_id: str) -> Dict[str, Any]:
        """
        Execute a single test case

        Args:
            test_case: TestCase database model instance
            container_id: Drools container ID

        Returns:
            Execution result dictionary
        """
        execution_id = str(uuid.uuid4())
        start_time = time.time()

        # Prepare request payload for Drools
        # Insert facts and fire rules, then query for Decision object
        commands = []

        # Insert applicant if present
        if test_case.applicant_data:
            # Map test data fields to Drools schema dynamically
            if self.field_mapper:
                applicant_mapped = self.field_mapper.map_applicant_data(test_case.applicant_data)
            else:
                # Fallback to legacy static mapping if no mapper available
                applicant_mapped = self._map_applicant_data(test_case.applicant_data)

            commands.append({
                "insert": {
                    "object": {
                        "com.underwriting.rules.Applicant": applicant_mapped
                    },
                    "out-identifier": "applicant",
                    "return-object": True
                }
            })

        # Insert policy if present
        if test_case.policy_data:
            # Map test data fields to Drools schema dynamically
            if self.field_mapper:
                policy_mapped = self.field_mapper.map_policy_data(test_case.policy_data)
            else:
                # Fallback to legacy static mapping if no mapper available
                policy_mapped = self._map_policy_data(test_case.policy_data)

            commands.append({
                "insert": {
                    "object": {
                        "com.underwriting.rules.Policy": policy_mapped
                    },
                    "out-identifier": "policy",
                    "return-object": True
                }
            })

        # Fire all rules
        commands.append({
            "fire-all-rules": {
                "max": -1
            }
        })

        # Get all facts
        commands.append({
            "get-objects": {
                "out-identifier": "all-facts"
            }
        })

        # Drools KIE Server batch command format
        request_payload = {
            "lookup": None,
            "commands": commands
        }

        # Call Drools service if available
        if self.drools_service:
            try:
                response = self.drools_service.execute_rules(
                    container_id=container_id,
                    payload=request_payload
                )
                response_payload = response
            except Exception as e:
                logger.error(f"Drools execution error: {e}")
                response_payload = {"error": str(e)}
        else:
            # Fallback: Make HTTP request directly
            response_payload = self._execute_drools_http(container_id, request_payload)

        execution_time = int((time.time() - start_time) * 1000)  # milliseconds

        # Debug: Log the full response payload with pretty printing
        print(f"\n  ===== DEBUG: Full Drools Response =====")
        print(f"  Response type: {type(response_payload)}")
        if isinstance(response_payload, dict):
            print(f"  Response keys: {list(response_payload.keys())}")
            print(f"  Full response:\n{json.dumps(response_payload, indent=2)}")
        else:
            print(f"  Response value: {response_payload}")
        print(f"  ===== END DEBUG =====\n")

        logger.debug(f"Drools response payload: {json.dumps(response_payload, indent=2)}")

        # Extract actual results from response
        actual_decision, actual_reasons, actual_risk = self._extract_results(response_payload)

        # Compare with expected results
        test_passed, pass_reason, fail_reason = self._compare_results(
            expected_decision=test_case.expected_decision,
            actual_decision=actual_decision,
            expected_risk=test_case.expected_risk_category,
            actual_risk=actual_risk,
            expected_reasons=test_case.expected_reasons,
            actual_reasons=actual_reasons
        )

        # Save execution to database
        execution_record = {
            "test_case_id": test_case.id,
            "execution_id": execution_id,
            "container_id": container_id,
            "actual_decision": actual_decision,
            "actual_reasons": actual_reasons,
            "actual_risk_category": actual_risk,
            "request_payload": request_payload,
            "response_payload": response_payload,
            "test_passed": test_passed,
            "pass_reason": pass_reason if test_passed else None,
            "fail_reason": fail_reason if not test_passed else None,
            "execution_time_ms": execution_time,
            "executed_at": datetime.utcnow(),
            "executed_by": "system"
        }

        # Save to database
        self.db_service.save_test_execution(execution_record)

        return {
            "test_case_id": test_case.id,
            "test_case_name": test_case.test_case_name,
            "execution_id": execution_id,
            "test_passed": test_passed,
            "expected_decision": test_case.expected_decision,
            "actual_decision": actual_decision,
            "expected_risk": test_case.expected_risk_category,
            "actual_risk": actual_risk,
            "pass_reason": pass_reason,
            "fail_reason": fail_reason,
            "execution_time_ms": execution_time
        }

    def _execute_drools_http(self, container_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Drools rules via HTTP"""
        try:
            # Get container endpoint from database
            container = self.db_service.get_container(container_id)
            if not container:
                raise ValueError(f"Container not found: {container_id}")

            # Build URL
            endpoint = container.endpoint or "http://drools:8080"
            url = f"{endpoint}/kie-server/services/rest/server/containers/instances/{container_id}"

            # Execute
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                auth=("kieserver", "kieserver1!"),
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}

        except Exception as e:
            logger.error(f"HTTP execution failed: {e}")
            return {"error": str(e)}

    def _extract_results(self, response_payload: Dict[str, Any]) -> Tuple[Optional[str], List[str], Optional[int]]:
        """
        Extract decision, reasons, and risk category from Drools response
        Based on the extraction logic from DroolsService

        Returns:
            Tuple of (decision, reasons, risk_category)
        """
        try:
            decision = None
            reasons = []
            risk_category = None
            all_facts = []

            # Debug: Print the full response structure
            logger.debug(f"Extracting results from response: {json.dumps(response_payload, indent=2)}")

            # Navigate through Drools KIE Server response structure
            if "result" in response_payload:
                exec_results = response_payload["result"].get("execution-results", {})
                results_list = exec_results.get("results", [])

                # Extract all results
                for idx, result in enumerate(results_list):
                    key = result.get("key", "")
                    value = result.get("value", {})

                    logger.debug(f"Processing result item {idx}: key={key}, value type={type(value)}")

                    if key == "all-facts":
                        # This is a list of all objects in working memory
                        all_facts = value if isinstance(value, list) else []
                        logger.debug(f"Found all-facts list with {len(all_facts)} objects")

                # Look for Decision object in all-facts list
                if all_facts:
                    for fact in all_facts:
                        if isinstance(fact, dict):
                            logger.debug(f"Examining fact: {list(fact.keys())}")

                            # Check if this is a wrapped Decision object (class name as key)
                            # Format: {"com.underwriting.rules.Decision": {decision: "approved", ...}}
                            for fact_key, fact_value in fact.items():
                                if "Decision" in fact_key and isinstance(fact_value, dict):
                                    logger.debug(f"Found Decision object with key: {fact_key}")
                                    # Handle both string 'decision' field and boolean 'approved' field
                                    decision_value = fact_value.get("decision") or fact_value.get("approved")
                                    if isinstance(decision_value, bool):
                                        decision = "approved" if decision_value else "rejected"
                                    else:
                                        decision = decision_value
                                    reasons = fact_value.get("reasons", [])
                                    # IMPORTANT: Extract risk category from Decision object
                                    risk_category = fact_value.get("riskCategory")
                                    logger.debug(f"Extracted decision={decision}, reasons={reasons}, risk_category={risk_category}")

                                # Check for RiskCategory object (separate object, less common)
                                elif "RiskCategory" in fact_key and isinstance(fact_value, dict):
                                    logger.debug(f"Found RiskCategory object with key: {fact_key}")
                                    # Only set if not already set from Decision object
                                    if risk_category is None:
                                        risk_category = fact_value.get("category") or fact_value.get("riskCategory")
                                        logger.debug(f"Extracted risk_category={risk_category}")

                            # Also check if this is a direct Decision object (no wrapper)
                            if not decision and ("decision" in fact or "approved" in fact):
                                decision_value = fact.get("decision") or fact.get("approved")
                                if isinstance(decision_value, bool):
                                    decision = "approved" if decision_value else "rejected"
                                else:
                                    decision = decision_value
                                reasons = fact.get("reasons", [])
                                # Also extract risk category from direct Decision object
                                if risk_category is None:
                                    risk_category = fact.get("riskCategory")
                                logger.debug(f"Found direct Decision fields: decision={decision}, reasons={reasons}, risk_category={risk_category}")

                            # Check for risk category in direct RiskCategory object (if not already found)
                            if risk_category is None and ("category" in fact or "riskCategory" in fact):
                                risk_category = fact.get("category") or fact.get("riskCategory")
                                logger.debug(f"Found direct risk category: {risk_category}")

            logger.debug(f"Final extracted values: decision={decision}, reasons={reasons}, risk_category={risk_category}")
            return decision, reasons, risk_category

        except Exception as e:
            logger.error(f"Error extracting results: {e}", exc_info=True)
            return None, [], None

    def _compare_results(self,
                        expected_decision: Optional[str],
                        actual_decision: Optional[str],
                        expected_risk: Optional[int],
                        actual_risk: Optional[int],
                        expected_reasons: Optional[List[str]],
                        actual_reasons: Optional[List[str]]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Compare expected vs actual results

        Returns:
            Tuple of (test_passed, pass_reason, fail_reason)
        """
        failures = []

        # Compare decision
        if expected_decision and actual_decision != expected_decision:
            failures.append(f"Decision mismatch: expected '{expected_decision}', got '{actual_decision}'")

        # Compare risk category
        if expected_risk is not None and actual_risk != expected_risk:
            failures.append(f"Risk category mismatch: expected {expected_risk}, got {actual_risk}")

        # Compare reasons (if both are provided)
        if expected_reasons and actual_reasons:
            # Check if all expected reasons are in actual reasons
            missing_reasons = [r for r in expected_reasons if r not in actual_reasons]
            if missing_reasons:
                failures.append(f"Missing expected reasons: {', '.join(missing_reasons)}")

        if failures:
            return False, None, "; ".join(failures)
        else:
            return True, "All assertions passed", None

    def _map_applicant_data(self, applicant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        [DEPRECATED - LEGACY FALLBACK ONLY]
        Static mapping for test case applicant data fields to Drools schema.

        This is a LEGACY fallback used only when IntelligentFieldMapper is not available.
        The system should use dynamic field mapping via IntelligentFieldMapper instead.

        Test cases use readable field names like 'healthStatus', 'criminalRecord'
        Drools expects specific field names like 'health', 'felonyConviction', 'duiconviction'
        """
        logger.warning("Using legacy static field mapping for applicant data. "
                      "Consider using IntelligentFieldMapper for dynamic mapping.")

        mapped = applicant_data.copy()

        # HARDCODED: Map healthStatus -> health
        if 'healthStatus' in mapped:
            mapped['health'] = mapped.pop('healthStatus')

        # HARDCODED: Map criminalRecord -> felonyConviction and duiconviction
        if 'criminalRecord' in mapped:
            criminal_record = mapped.pop('criminalRecord')
            mapped['felonyConviction'] = criminal_record.lower() == 'felony'
            mapped['duiconviction'] = criminal_record.lower() == 'dui'

        return mapped

    def _map_policy_data(self, policy_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        [DEPRECATED - LEGACY FALLBACK ONLY]
        Static mapping for test case policy data fields to Drools schema.

        This is a LEGACY fallback used only when IntelligentFieldMapper is not available.
        The system should use dynamic field mapping via IntelligentFieldMapper instead.

        Test cases use readable field names like 'termYears'
        Drools expects 'term'
        """
        logger.warning("Using legacy static field mapping for policy data. "
                      "Consider using IntelligentFieldMapper for dynamic mapping.")

        mapped = policy_data.copy()

        # HARDCODED: Map termYears -> term
        if 'termYears' in mapped:
            mapped['term'] = mapped.pop('termYears')

        return mapped
