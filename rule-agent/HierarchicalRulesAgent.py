"""
Hierarchical Rules Agent
Analyzes policy documents and generates hierarchical rules with parent-child dependencies
"""

import json
from typing import Dict, List, Any


class HierarchicalRulesAgent:
    """
    Uses LLM to generate hierarchical rules from policy documents.
    Rules are organized in a tree structure with parent-child dependencies.
    """

    def __init__(self, llm):
        """
        Initialize the agent with an LLM

        :param llm: Language model instance (e.g., ChatOpenAI)
        """
        self.llm = llm

    def generate_hierarchical_rules(self, policy_text: str, policy_type: str = "general") -> List[Dict[str, Any]]:
        """
        Generate hierarchical rules from policy document

        :param policy_text: Full text of the policy document
        :param policy_type: Type of policy (insurance, loan, etc.)
        :return: List of root-level rules with nested dependencies
        """

        prompt = f"""You are an expert underwriting rules analyst. Analyze the following {policy_type} policy document and generate a hierarchical structure of underwriting rules.

IMPORTANT INSTRUCTIONS:
1. Create a tree structure with parent rules and child dependencies
2. Each rule should have:
   - id: Dot notation (e.g., "1", "1.1", "1.1.1")
   - name: Brief descriptive name
   - description: Detailed explanation of what the rule checks
   - expected: What is expected (condition/requirement)
   - actual: What would be checked/validated (leave as placeholder if not evaluating)
   - confidence: Your confidence in extracting this rule (0.0 to 1.0)
   - passed: null (will be determined during evaluation)
   - page_number: Page number in the document where this rule is found (integer)
   - clause_reference: Clause/section reference (e.g., "Article II, Section 2.1", "Clause 5.2")
   - dependencies: Array of child rules (can be nested unlimited levels)

3. Organize rules logically:
   - Top-level rules should be major decision categories (e.g., "Eligibility Check", "Risk Assessment", "Coverage Calculation")
   - Child rules should break down the parent into specific checks
   - Use deep nesting where rules naturally depend on sub-checks

4. Use dot notation IDs that reflect the hierarchy:
   - "1" = first top-level rule
   - "1.1" = first child of rule 1
   - "1.1.1" = first grandchild of rule 1.1
   - etc.

5. Return ONLY valid JSON - no markdown, no explanation, no extra text.

POLICY DOCUMENT:
{policy_text[:15000]}

Return a JSON array of top-level rules with nested dependencies. Example structure:
[
  {{
    "id": "1",
    "name": "Eligibility Verification",
    "description": "Verify applicant meets all basic eligibility requirements",
    "expected": "All eligibility criteria met",
    "actual": "To be evaluated",
    "confidence": 0.95,
    "passed": null,
    "page_number": 3,
    "clause_reference": "Article II",
    "dependencies": [
      {{
        "id": "1.1",
        "name": "Age Requirement Check",
        "description": "Verify applicant age is within acceptable range",
        "expected": "Age between 18 and 65",
        "actual": "To be evaluated",
        "confidence": 0.98,
        "passed": null,
        "page_number": 3,
        "clause_reference": "Article II, Section 2.1",
        "dependencies": [
          {{
            "id": "1.1.1",
            "name": "Minimum Age Check",
            "description": "Verify applicant is at least 18 years old",
            "expected": "Age >= 18",
            "actual": "To be evaluated",
            "confidence": 0.99,
            "passed": null,
            "page_number": 3,
            "clause_reference": "Article II, Section 2.1.1",
            "dependencies": []
          }},
          {{
            "id": "1.1.2",
            "name": "Maximum Age Check",
            "description": "Verify applicant is not older than 65 years",
            "expected": "Age <= 65",
            "actual": "To be evaluated",
            "confidence": 0.99,
            "passed": null,
            "page_number": 3,
            "clause_reference": "Article II, Section 2.1.2",
            "dependencies": []
          }}
        ]
      }},
      {{
        "id": "1.2",
        "name": "Credit Score Check",
        "description": "Verify minimum credit score requirement",
        "expected": "Credit score >= 600",
        "actual": "To be evaluated",
        "confidence": 0.92,
        "passed": null,
        "page_number": 5,
        "clause_reference": "Article III, Section 3.1",
        "dependencies": []
      }}
    ]
  }}
]

CRITICAL: Include page_number and clause_reference for EVERY rule at all levels of the hierarchy. Look for section headers, article numbers, and clause references in the policy document.

Generate comprehensive hierarchical rules now:"""

        try:
            print("🤖 Invoking LLM to generate hierarchical rules...")

            # Get response from LLM
            response = self.llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            print(f"✓ LLM response received ({len(response_text)} characters)")

            # Clean up response - remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Parse JSON response
            hierarchical_rules = json.loads(response_text)

            # Validate structure
            if not isinstance(hierarchical_rules, list):
                raise ValueError("Expected a list of rules at the top level")

            # Count total rules
            def count_rules(rules):
                count = len(rules)
                for rule in rules:
                    if rule.get('dependencies'):
                        count += count_rules(rule['dependencies'])
                return count

            total_rules = count_rules(hierarchical_rules)
            print(f"✓ Generated {len(hierarchical_rules)} top-level rules with {total_rules} total rules in hierarchy")

            # Print tree structure for verification
            def print_tree(rules, indent=0):
                for rule in rules:
                    print(f"{'  ' * indent}├─ {rule['id']}: {rule['name']}")
                    if rule.get('dependencies'):
                        print_tree(rule['dependencies'], indent + 1)

            print("\n📋 Hierarchical Rules Structure:")
            print_tree(hierarchical_rules)

            return hierarchical_rules

        except json.JSONDecodeError as e:
            print(f"✗ Failed to parse LLM response as JSON: {e}")
            print(f"Response was: {response_text[:500]}...")
            raise ValueError(f"LLM did not return valid JSON: {e}")

        except Exception as e:
            print(f"✗ Error generating hierarchical rules: {e}")
            raise

    def validate_rule_structure(self, rule: Dict[str, Any]) -> bool:
        """
        Validate that a rule has the required structure

        :param rule: Rule dictionary to validate
        :return: True if valid, False otherwise
        """
        required_fields = ['id', 'name', 'description', 'expected', 'confidence']

        for field in required_fields:
            if field not in rule:
                print(f"⚠ Rule missing required field: {field}")
                return False

        # Validate dependencies if present
        if 'dependencies' in rule and rule['dependencies']:
            if not isinstance(rule['dependencies'], list):
                print(f"⚠ Rule dependencies must be a list")
                return False

            # Recursively validate child rules
            for child in rule['dependencies']:
                if not self.validate_rule_structure(child):
                    return False

        return True

    def flatten_hierarchical_rules(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Flatten hierarchical rules into a list for easier processing
        (Maintains parent-child relationships via rule IDs)

        :param rules: Hierarchical rules list
        :return: Flattened list of all rules
        """
        flattened = []

        def flatten_recursive(rule_list, parent_id=None):
            for rule in rule_list:
                rule_copy = rule.copy()
                dependencies = rule_copy.pop('dependencies', [])

                if parent_id:
                    rule_copy['parent_rule_id'] = parent_id

                flattened.append(rule_copy)

                # Process children
                if dependencies:
                    flatten_recursive(dependencies, rule['id'])

        flatten_recursive(rules)
        return flattened
