"""
Intelligent Field Mapper
Uses LLM to dynamically map test data fields to Drools schema fields
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class IntelligentFieldMapper:
    """
    Dynamically maps test data field names to Drools schema field names using LLM.
    Eliminates hardcoded field mappings.
    """

    # Common field name aliases (fallback mappings)
    COMMON_FIELD_ALIASES = {
        'healthConditions': 'health',
        'healthStatus': 'health',
        'health_status': 'health',
        'health_conditions': 'health',
        'smoking': 'smoker',
        'is_smoker': 'smoker',
        'hazardous_occupation': 'hazardousOccupation',
        'is_hazardous': 'hazardousOccupation',
        'credit_score': 'creditScore',
        'annual_income': 'annualIncome',
        'debt_to_income_ratio': 'debtToIncomeRatio',
        'criminal_record': 'criminalRecord',
        'has_criminal_record': 'criminalRecord',
    }

    def __init__(self, llm, schema: Dict[str, Any] = None):
        """
        Initialize the field mapper

        Args:
            llm: Language model instance for intelligent mapping
            schema: Schema dictionary from DynamicSchemaGenerator
        """
        self.llm = llm
        self.schema = schema or {}
        self.mapping_cache = {}  # Cache for performance

    def update_schema(self, schema: Dict[str, Any]):
        """Update the schema used for mapping"""
        self.schema = schema
        self.mapping_cache = {}  # Clear cache when schema changes

    def map_test_data(self,
                      test_data: Dict[str, Any],
                      entity_type: str) -> Dict[str, Any]:
        """
        Map test data fields to schema fields dynamically

        Priority order:
        1. Common field aliases (fastest)
        2. Schema field_mappings
        3. LLM-based intelligent mapping (slowest)

        Args:
            test_data: Raw test data with arbitrary field names
            entity_type: Either "applicant" or "policy"

        Returns:
            Mapped data with schema-compliant field names
        """
        # STEP 1: Apply common field aliases first (fastest path)
        aliased_data = {}
        for key, value in test_data.items():
            # Check if this field has a known alias
            mapped_key = self.COMMON_FIELD_ALIASES.get(key, key)
            aliased_data[mapped_key] = value

        logger.debug(f"Applied common field aliases for {entity_type}: {list(test_data.keys())} -> {list(aliased_data.keys())}")

        # STEP 2: Try using the field_mappings from schema (fast path)
        if self.schema.get('field_mappings'):
            mapped_data = self._apply_static_mappings(aliased_data, self.schema['field_mappings'])
            # Check if all fields were mapped successfully
            if all(key in mapped_data or key in self._get_schema_fields(entity_type)
                   for key in aliased_data.keys()):
                logger.debug(f"Successfully mapped {entity_type} data using static mappings")
                return mapped_data

        # STEP 3: Fallback to LLM-based intelligent mapping
        logger.info(f"Using LLM for intelligent mapping of {entity_type} data...")
        return self._llm_based_mapping(aliased_data, entity_type)

    def _apply_static_mappings(self,
                               test_data: Dict[str, Any],
                               mappings: Dict[str, str]) -> Dict[str, Any]:
        """Apply static field mappings from schema"""
        mapped = {}
        for key, value in test_data.items():
            # Check if there's a mapping for this field
            if key in mappings:
                mapped[mappings[key]] = value
            else:
                # Keep original field name
                mapped[key] = value
        return mapped

    def _get_schema_fields(self, entity_type: str) -> list:
        """Get list of field names for given entity type"""
        if entity_type == "applicant":
            return [f['field_name'] for f in self.schema.get('applicant_fields', [])]
        elif entity_type == "policy":
            return [f['field_name'] for f in self.schema.get('policy_fields', [])]
        return []

    def _llm_based_mapping(self,
                          test_data: Dict[str, Any],
                          entity_type: str) -> Dict[str, Any]:
        """Use LLM to intelligently map fields"""
        # Get schema fields for this entity type
        schema_fields = []
        if entity_type == "applicant" and self.schema.get('applicant_fields'):
            schema_fields = self.schema['applicant_fields']
        elif entity_type == "policy" and self.schema.get('policy_fields'):
            schema_fields = self.schema['policy_fields']

        if not schema_fields:
            logger.warning(f"No schema fields found for {entity_type}, returning original data")
            return test_data

        # Create cache key
        cache_key = f"{entity_type}_{json.dumps(sorted(test_data.keys()))}"
        if cache_key in self.mapping_cache:
            logger.debug(f"Using cached mapping for {entity_type}")
            return self._apply_cached_mapping(test_data, self.mapping_cache[cache_key])

        # Build schema context
        schema_context = self._build_schema_context(schema_fields)

        # Create the prompt
        prompt = self._create_mapping_prompt(test_data, schema_context, entity_type)

        try:
            response = self.llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Parse mapping from response
            mapping = self._parse_mapping_response(response_text)

            # Cache the mapping
            self.mapping_cache[cache_key] = mapping

            # Apply the mapping
            return self._apply_mapping(test_data, mapping)

        except Exception as e:
            logger.error(f"Error in LLM-based mapping: {e}")
            logger.warning(f"Returning original data for {entity_type}")
            return test_data

    def _build_schema_context(self, schema_fields: list) -> str:
        """Build context string describing the schema"""
        context = []
        for field in schema_fields:
            field_info = (f"- {field['field_name']} ({field['field_type']}): "
                         f"{field['description']}")
            if field.get('common_aliases'):
                field_info += f" [aliases: {', '.join(field['common_aliases'])}]"
            context.append(field_info)
        return "\n".join(context)

    def _create_mapping_prompt(self,
                               test_data: Dict[str, Any],
                               schema_context: str,
                               entity_type: str) -> str:
        """Create prompt for LLM-based field mapping"""
        return f"""You are a data mapping expert. Your task is to map test data field names to the correct schema field names.

# Test Data Fields ({entity_type}):
{json.dumps(test_data, indent=2)}

# Schema Fields Available:
{schema_context}

# Instructions:

1. For each field in the test data, determine which schema field it should map to
2. Consider:
   - Field name similarity (e.g., "healthStatus" → "health")
   - Semantic meaning (e.g., "criminalRecord" could map to "felonyConviction" or multiple fields)
   - Data type compatibility
   - Common aliases listed in the schema

3. Handle special cases:
   - If one test field should map to multiple schema fields, split it appropriately
     Example: "criminalRecord": "felony" → {{"felonyConviction": true, "duiconviction": false}}
   - If a test field has no matching schema field, mark it as "UNMAPPED"
   - Preserve data types and values during mapping

4. Return ONLY valid JSON with this structure:

```json
{{
  "mappings": [
    {{
      "test_field": "healthStatus",
      "schema_field": "health",
      "action": "rename"
    }},
    {{
      "test_field": "criminalRecord",
      "schema_field": "felonyConviction",
      "action": "transform",
      "transform_logic": "value.lower() == 'felony'"
    }},
    {{
      "test_field": "termYears",
      "schema_field": "term",
      "action": "rename"
    }}
  ]
}}
```

Actions:
- "rename": Simple field name change, keep value as-is
- "transform": Field needs value transformation (provide transform_logic)
- "split": One test field maps to multiple schema fields (provide multiple mappings)

Generate the mapping now:"""

    def _parse_mapping_response(self, response_text: str) -> Dict[str, Any]:
        """Parse mapping from LLM response"""
        try:
            # Extract JSON from markdown code blocks
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
            mapping = json.loads(json_text)

            if not isinstance(mapping.get('mappings'), list):
                raise ValueError("mappings must be a list")

            return mapping

        except Exception as e:
            logger.error(f"Error parsing mapping JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            raise

    def _apply_mapping(self,
                      test_data: Dict[str, Any],
                      mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the mapping to transform test data"""
        mapped_data = {}

        for mapping_rule in mapping.get('mappings', []):
            test_field = mapping_rule.get('test_field')
            schema_field = mapping_rule.get('schema_field')
            action = mapping_rule.get('action', 'rename')

            if test_field not in test_data:
                continue

            test_value = test_data[test_field]

            if action == 'rename':
                # Simple rename
                mapped_data[schema_field] = test_value

            elif action == 'transform':
                # Apply transformation logic
                transform_logic = mapping_rule.get('transform_logic', '')
                try:
                    # Safe evaluation context
                    eval_context = {'value': test_value}
                    transformed_value = eval(transform_logic, {"__builtins__": {}}, eval_context)
                    mapped_data[schema_field] = transformed_value
                except Exception as e:
                    logger.warning(f"Transform failed for {test_field}: {e}, using original value")
                    mapped_data[schema_field] = test_value

            elif action == 'split':
                # Field splits into multiple schema fields
                # This is handled by multiple mapping rules with same test_field
                mapped_data[schema_field] = test_value

        # Add any test fields that weren't mapped (pass-through)
        for key, value in test_data.items():
            if key not in [m['test_field'] for m in mapping.get('mappings', [])]:
                mapped_data[key] = value

        return mapped_data

    def _apply_cached_mapping(self,
                             test_data: Dict[str, Any],
                             cached_mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a previously cached mapping"""
        return self._apply_mapping(test_data, cached_mapping)

    def map_applicant_data(self, applicant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenience method to map applicant test data

        Args:
            applicant_data: Raw applicant test data

        Returns:
            Mapped applicant data
        """
        return self.map_test_data(applicant_data, "applicant")

    def map_policy_data(self, policy_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenience method to map policy test data

        Args:
            policy_data: Raw policy test data

        Returns:
            Mapped policy data
        """
        return self.map_test_data(policy_data, "policy")
