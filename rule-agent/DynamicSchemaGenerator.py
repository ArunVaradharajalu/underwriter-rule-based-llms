"""
Dynamic Schema Generator
Extracts field definitions from policy documents using LLM to generate dynamic Drools schemas
"""

import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DynamicSchemaGenerator:
    """
    Dynamically generates Drools schema definitions from policy documents.
    Eliminates hardcoded field names and types.
    """

    def __init__(self, llm):
        """
        Initialize the schema generator

        Args:
            llm: Language model instance for schema extraction
        """
        self.llm = llm

    def generate_schema_from_policy(self,
                                    policy_text: str,
                                    extracted_queries: List[Dict[str, Any]] = None,
                                    policy_type: str = "insurance") -> Dict[str, Any]:
        """
        Generate dynamic schema definitions from policy document

        Args:
            policy_text: Full policy document text
            extracted_queries: Previously extracted queries/rules from the document
            policy_type: Type of policy (insurance, loan, etc.)

        Returns:
            Dictionary containing:
            - applicant_fields: List of field definitions for Applicant entity
            - policy_fields: List of field definitions for Policy entity
            - field_mappings: Suggested mappings between common names and schema names
        """
        logger.info("Generating dynamic schema from policy document...")

        # Build context from extracted queries if available
        queries_context = ""
        if extracted_queries:
            queries_context = "\n\nPreviously extracted requirements:\n"
            for q in extracted_queries[:20]:  # Limit to first 20
                # Handle both dict and string query formats
                if isinstance(q, dict):
                    query_text = q.get('query_text', q.get('question', str(q)))
                else:
                    query_text = str(q)
                queries_context += f"- {query_text}\n"

        # Create the prompt for LLM
        prompt = self._create_schema_extraction_prompt(policy_text, queries_context, policy_type)

        try:
            response = self.llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Parse JSON from response
            schema = self._parse_schema_response(response_text)

            logger.info(f"Generated schema with {len(schema.get('applicant_fields', []))} applicant fields "
                       f"and {len(schema.get('policy_fields', []))} policy fields")

            return schema

        except Exception as e:
            logger.error(f"Error generating schema: {e}")
            # Return minimal schema as fallback
            return self._generate_minimal_schema(policy_type)

    def _create_schema_extraction_prompt(self, policy_text: str, queries_context: str, policy_type: str) -> str:
        """Create the LLM prompt for schema extraction"""
        return f"""You are a schema extraction expert for {policy_type} underwriting systems.

Your task is to analyze the policy document and extract ALL data fields that would be needed to evaluate applications according to this policy.

# Policy Document:
{policy_text[:10000]}... (truncated for brevity)

{queries_context}

# Instructions:

1. Identify ALL fields that describe an **Applicant** (person/entity applying for the policy):
   - Demographics (age, gender, location, etc.)
   - Financial attributes (income, credit score, assets, etc.)
   - Health/medical information (health status, pre-existing conditions, smoker status, etc.)
   - Employment information (occupation, employer, years employed, etc.)
   - Legal/criminal record information
   - Any other applicant-specific attributes mentioned in the policy

2. Identify ALL fields that describe the **Policy** being applied for:
   - Coverage details (amount, type, duration, etc.)
   - Premium information
   - Terms and conditions
   - Special features or riders
   - Any other policy-specific attributes

3. For each field, provide:
   - **field_name**: Camel case name (e.g., "annualIncome", "creditScore", "healthStatus")
   - **field_type**: One of ["String", "int", "double", "boolean", "Date"]
   - **description**: Brief description of what this field represents
   - **example_values**: Array of 2-3 example values for this field
   - **common_aliases**: Array of alternative names this field might be called in test data (e.g., ["income", "yearly_income", "annual_income"] for annualIncome)

4. Also provide **field_mappings**: A mapping from common/readable field names to the schema field names.
   - This helps map test data that uses user-friendly names (like "healthStatus") to schema names (like "health")
   - Include bidirectional mappings for flexibility

# Output Format:

Return ONLY valid JSON with this structure:

```json
{{
  "applicant_fields": [
    {{
      "field_name": "age",
      "field_type": "int",
      "description": "Applicant's age in years",
      "example_values": [25, 45, 60],
      "common_aliases": ["age", "applicantAge", "yearsOld"]
    }},
    {{
      "field_name": "annualIncome",
      "field_type": "double",
      "description": "Applicant's annual income in dollars",
      "example_values": [50000, 75000, 120000],
      "common_aliases": ["income", "yearly_income", "annual_income", "salary"]
    }},
    {{
      "field_name": "health",
      "field_type": "String",
      "description": "Overall health status of applicant",
      "example_values": ["excellent", "good", "fair"],
      "common_aliases": ["healthStatus", "health_status", "health_condition", "health"]
    }},
    {{
      "field_name": "smoker",
      "field_type": "boolean",
      "description": "Whether applicant is a smoker",
      "example_values": [true, false],
      "common_aliases": ["smoker", "isSmoker", "smoking", "tobacco_user"]
    }}
  ],
  "policy_fields": [
    {{
      "field_name": "coverageAmount",
      "field_type": "double",
      "description": "Amount of coverage in dollars",
      "example_values": [250000, 500000, 1000000],
      "common_aliases": ["coverage", "coverageAmount", "insured_amount", "coverage_amt"]
    }},
    {{
      "field_name": "term",
      "field_type": "int",
      "description": "Policy term duration in years",
      "example_values": [10, 20, 30],
      "common_aliases": ["term", "termYears", "duration", "policy_term"]
    }}
  ],
  "field_mappings": {{
    "healthStatus": "health",
    "health_status": "health",
    "health_condition": "health",
    "termYears": "term",
    "term_years": "term",
    "duration": "term",
    "isSmoker": "smoker",
    "smoking": "smoker",
    "annualIncome": "annualIncome",
    "yearly_income": "annualIncome"
  }}
}}
```

CRITICAL: Be comprehensive - extract ALL fields mentioned or implied by the policy rules. Missing a field will cause test failures.

Generate the schema now:"""

    def _parse_schema_response(self, response_text: str) -> Dict[str, Any]:
        """Parse schema from LLM response"""
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                # Try to find JSON object directly
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                json_text = response_text[json_start:json_end].strip()

            # Parse JSON
            schema = json.loads(json_text)

            # Validate structure
            if not isinstance(schema.get('applicant_fields'), list):
                raise ValueError("applicant_fields must be a list")
            if not isinstance(schema.get('policy_fields'), list):
                raise ValueError("policy_fields must be a list")
            if not isinstance(schema.get('field_mappings'), dict):
                raise ValueError("field_mappings must be a dictionary")

            return schema

        except Exception as e:
            logger.error(f"Error parsing schema JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            raise

    def _generate_minimal_schema(self, policy_type: str) -> Dict[str, Any]:
        """Generate minimal schema as fallback when LLM fails"""
        logger.info("Generating minimal schema as fallback...")

        return {
            "applicant_fields": [
                {
                    "field_name": "name",
                    "field_type": "String",
                    "description": "Applicant name",
                    "example_values": ["John Doe", "Jane Smith"],
                    "common_aliases": ["name", "applicantName", "full_name"]
                },
                {
                    "field_name": "age",
                    "field_type": "int",
                    "description": "Applicant age",
                    "example_values": [25, 45, 60],
                    "common_aliases": ["age", "applicantAge"]
                }
            ],
            "policy_fields": [
                {
                    "field_name": "policyType",
                    "field_type": "String",
                    "description": "Type of policy",
                    "example_values": ["term_life", "whole_life"],
                    "common_aliases": ["policyType", "type", "policy_type"]
                }
            ],
            "field_mappings": {
                "applicantAge": "age",
                "policy_type": "policyType"
            }
        }

    def generate_drools_declarations(self, schema: Dict[str, Any]) -> str:
        """
        Generate Drools DRL declare statements from schema

        Args:
            schema: Schema dictionary with applicant_fields and policy_fields

        Returns:
            String containing Drools declare statements
        """
        drl = ""

        # Generate Applicant declaration
        if schema.get('applicant_fields'):
            drl += "declare Applicant\n"
            for field in schema['applicant_fields']:
                field_name = field['field_name']
                field_type = field['field_type']
                drl += f"    {field_name}: {field_type}\n"
            drl += "end\n\n"

        # Generate Policy declaration
        if schema.get('policy_fields'):
            drl += "declare Policy\n"
            for field in schema['policy_fields']:
                field_name = field['field_name']
                field_type = field['field_type']
                drl += f"    {field_name}: {field_type}\n"
            drl += "end\n\n"

        # Always include Decision declaration (standard output)
        drl += """declare Decision
    decision: String
    approved: boolean
    reasons: java.util.List
    riskCategory: int
end
"""

        return drl
