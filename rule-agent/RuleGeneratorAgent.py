#
#    Copyright 2024 IBM Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
from langchain_core.prompts import ChatPromptTemplate
import pandas as pd
from typing import Dict
import json
import os
import io

class RuleGeneratorAgent:
    """
    Converts extracted policy data into Drools rules (DRL format and decision tables)
    """

    def __init__(self, llm):
        self.llm = llm

        # New prompt for hierarchical rule generation
        self.hierarchical_rule_generation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in insurance underwriting rules and Drools rule engine.

Given extracted policy data, generate executable Drools DRL (Drools Rule Language) rules organized into THREE PRIORITY LEVELS.

**CRITICAL: Rules must be categorized into 3 levels based on importance:**

**LEVEL 1 - Critical/Knockout Rules (Most Important)**
- Rules that immediately disqualify an application
- Hard requirements that MUST be met
- Examples: Minimum age, maximum age, citizenship requirements, license validity, property existence
- These are "showstoppers" - if any fail, no need to check further rules

**LEVEL 2 - Standard/Important Rules**
- Important risk assessment rules
- Policy limits and standard underwriting criteria
- Examples: Income vs coverage ratios, occupation risk categories, credit score thresholds, property condition
- These are checked only if Level 1 passes

**LEVEL 3 - Preferred/Optimal Rules**
- Nice-to-have criteria for preferred rates
- Fine-grained risk adjustments
- Examples: Premium adjustments for lifestyle factors, discounts for bundling, loyalty bonuses
- These are checked only if Level 1 and Level 2 pass

IMPORTANT: Use 'declare' statements to define types directly in the DRL file. Do NOT import external Java classes.

Each level should be a complete, self-contained DRL file with the following structure:

```drl
package com.underwriting.rules;

// Declare types directly in DRL (no external Java classes needed)
declare Applicant
    name: String
    age: int
    occupation: String
    healthConditions: String
end

declare Policy
    policyType: String
    coverageAmount: double
    term: int
end

declare Decision
    approved: boolean
    reasons: java.util.List
    requiresManualReview: boolean
    premiumMultiplier: double
end

// Rules using the declared types
rule "Initialize Decision"
    when
        not Decision()
    then
        Decision decision = new Decision();
        decision.setApproved(true);
        decision.setReasons(new java.util.ArrayList());
        decision.setRequiresManualReview(false);
        decision.setPremiumMultiplier(1.0);
        insert(decision);
end

rule "Age Requirement Check"
    when
        $applicant : Applicant( age < 18 || age > 65 )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.getReasons().add("Applicant age is outside acceptable range");
        update($decision);
end

rule "Coverage vs Income Limit Check"
    when
        $applicant : Applicant( $income : annualIncome )
        $policy : Policy( coverageAmount > ($income * 10) )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.getReasons().add("Coverage amount exceeds 10x annual income");
        update($decision);
end

rule "Age and Coverage Combined Check"
    when
        $applicant : Applicant( age > 50, $income : annualIncome )
        $policy : Policy( coverageAmount > 500000, coverageAmount > ($income * 5) )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.getReasons().add("High coverage requires manual review for age 50+");
        update($decision);
end
```

Guidelines for EACH level:
1. ALWAYS use 'declare' statements to define Applicant, Policy, and Decision types at the top of EACH DRL file
2. Do NOT use import statements for model classes
3. **CRITICAL**: Every field you reference in rules MUST be declared in the type definition. If you use `loanType` in a rule, you MUST add `loanType: String` in the declare statement.
4. **CRITICAL**: Before writing rules, first decide ALL fields needed and add them to the declare statements. Then write rules using only those declared fields.
5. **CRITICAL**: The same declare statements must be in ALL three levels with the SAME fields. Don't add fields in level 2 that weren't in level 1.
6. Include an "Initialize Decision" rule in EACH level that creates the Decision object if it doesn't exist
7. Use proper getter/setter methods (e.g., setApproved(), getReasons().add("reason"))
8. For rejection rules, use $decision.getReasons().add("reason text") to accumulate ALL rejection reasons
9. NEVER use setReason() or setReasons() - always use getReasons().add() to preserve all reasons
10. When comparing fields from different objects, use variable binding
11. Create clear, specific rule names with level indicator (e.g., "L1: Age Requirement Check")

**IMPORTANT OUTPUT FORMAT:**

You MUST generate THREE separate DRL files. Format your response like this:

```level1-drl
package com.underwriting.rules;

// LEVEL 1: Critical/Knockout Rules
declare Applicant
    ...
end

declare Policy
    ...
end

declare Decision
    approved: boolean
    reasons: java.util.List
    ...
end

rule "Initialize Decision"
    ...
end

rule "L1: [Rule Name]"
    ...
end
```

```level2-drl
package com.underwriting.rules;

// LEVEL 2: Standard/Important Rules
declare Applicant
    ...
end

// ... same declares ...

rule "Initialize Decision"
    ...
end

rule "L2: [Rule Name]"
    ...
end
```

```level3-drl
package com.underwriting.rules;

// LEVEL 3: Preferred/Optimal Rules
declare Applicant
    ...
end

// ... same declares ...

rule "Initialize Decision"
    ...
end

rule "L3: [Rule Name]"
    ...
end
```

After the three code blocks, provide a brief explanation of how you categorized the rules.

DO NOT generate decision tables - only generate DRL rules."""),
            ("user", """Extracted policy data:

{extracted_data}

Generate THREE complete, self-contained Drools DRL files (level1, level2, level3) with 'declare' statements in each.""")
        ])

        # Original prompt for non-hierarchical generation (backwards compatibility)
        self.rule_generation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in insurance underwriting rules and Drools rule engine.

Given extracted policy data, generate executable Drools DRL (Drools Rule Language) rules.

IMPORTANT: Use 'declare' statements to define types directly in the DRL file. Do NOT import external Java classes.

The rules should follow this structure:

```drl
package com.underwriting.rules;

// Declare types directly in DRL (no external Java classes needed)
declare Applicant
    name: String
    age: int
    occupation: String
    healthConditions: String
end

declare Policy
    policyType: String
    coverageAmount: double
    term: int
end

declare Decision
    approved: boolean
    reasons: java.util.List
    requiresManualReview: boolean
    premiumMultiplier: double
end

// Rules using the declared types
rule "Initialize Decision"
    when
        not Decision()
    then
        Decision decision = new Decision();
        decision.setApproved(true);
        decision.setReasons(new java.util.ArrayList());
        decision.setRequiresManualReview(false);
        decision.setPremiumMultiplier(1.0);
        insert(decision);
end

rule "Age Requirement Check"
    when
        $applicant : Applicant( age < 18 || age > 65 )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.getReasons().add("Applicant age is outside acceptable range");
        update($decision);
end
```

Guidelines:
1. ALWAYS use 'declare' statements to define Applicant, Policy, and Decision types at the top of the DRL file
2. Do NOT use import statements for model classes
3. **CRITICAL**: Every field you reference in rules MUST be declared in the type definition. If you use `loanType` in a rule, you MUST add `loanType: String` in the declare statement.
4. **CRITICAL**: Before writing rules, first decide ALL fields needed and add them to the declare statements. Then write rules using only those declared fields.
5. Create clear, specific rule names based on the extracted data
6. Include an "Initialize Decision" rule that creates the Decision object if it doesn't exist
7. Use appropriate conditions based on the extracted data
8. Make rules executable and testable
9. Add comments explaining complex logic
10. Handle edge cases and validation
11. Use proper getter/setter methods (e.g., setApproved(), getReasons().add("reason"))
12. For rejection rules, use $decision.getReasons().add("reason text") to accumulate ALL rejection reasons
13. NEVER use setReason() or setReasons() in rejection rules - always use getReasons().add() to preserve all reasons
14. When comparing fields from different objects (e.g., Applicant.annualIncome vs Policy.coverageAmount), use variable binding: bind the field to a variable in one object pattern, then reference that variable in another object's constraint
15. CORRECT multi-object syntax: `$applicant : Applicant( $income : annualIncome )  $policy : Policy( coverageAmount > ($income * 10) )`
16. WRONG multi-object syntax: `$applicant : Applicant( annualIncome * 10 < coverageAmount )` - this will fail because coverageAmount is not on Applicant

Return your response with:
1. Complete DRL rules in ```drl code blocks (including declare statements)
2. Brief explanation of the rules

DO NOT generate decision tables - only generate DRL rules."""),
            ("user", """Extracted policy data:

{extracted_data}

Generate complete, self-contained Drools DRL rules with 'declare' statements for all types.""")
        ])

        self.chain = self.rule_generation_prompt | self.llm
        self.hierarchical_chain = self.hierarchical_rule_generation_prompt | self.llm

    def generate_rules(self, extracted_data: Dict) -> Dict[str, str]:
        """
        Generate Drools rules from extracted data

        :param extracted_data: Data extracted by Textract
        :return: Dictionary with 'drl', 'decision_table', and 'explanation' keys
        """
        try:
            result = self.chain.invoke({
                "extracted_data": json.dumps(extracted_data, indent=2)
            })

            # Parse LLM response to extract DRL and CSV
            content = result.content

            # Extract DRL (between ```drl or ```java and ```)
            drl = self._extract_code_block(content, 'drl') or \
                  self._extract_code_block(content, 'java')

            # Extract CSV (between ```csv and ```)
            decision_table = self._extract_code_block(content, 'csv')

            # Extract explanation (everything not in code blocks)
            explanation = self._extract_explanation(content)

            return {
                'drl': drl or "// No DRL rules generated",
                'decision_table': decision_table or "",
                'explanation': explanation,
                'raw_response': content
            }

        except Exception as e:
            print(f"Error generating rules: {e}")
            return {
                'drl': "// Error generating rules",
                'decision_table': "",
                'explanation': f"Error: {str(e)}",
                'raw_response': ""
            }

    def _extract_code_block(self, text: str, language: str) -> str:
        """Extract code block from markdown"""
        start_marker = f"```{language}"
        end_marker = "```"

        start = text.find(start_marker)
        if start == -1:
            return None

        start += len(start_marker)
        end = text.find(end_marker, start)

        if end == -1:
            return None

        return text[start:end].strip()

    def _extract_explanation(self, text: str) -> str:
        """Extract explanation text (non-code-block content)"""
        # Remove all code blocks
        import re
        cleaned = re.sub(r'```[\s\S]*?```', '', text)
        return cleaned.strip()

    def save_decision_table(self, decision_table: str, output_path: str):
        """
        Save decision table as Excel file for Drools

        :param decision_table: CSV content
        :param output_path: Path to save Excel file
        """
        try:
            if not decision_table:
                print("No decision table to save")
                return None

            # Convert CSV to DataFrame
            df = pd.read_csv(io.StringIO(decision_table))

            # Save as Excel
            df.to_excel(output_path, index=False)
            print(f"Decision table saved to: {output_path}")
            return output_path

        except Exception as e:
            print(f"Error saving decision table: {e}")
            # Try saving as CSV instead
            try:
                csv_path = output_path.replace('.xlsx', '.csv')
                with open(csv_path, 'w') as f:
                    f.write(decision_table)
                print(f"Decision table saved as CSV to: {csv_path}")
                return csv_path
            except Exception as e2:
                print(f"Error saving as CSV: {e2}")
                return None

    def generate_hierarchical_rules(self, extracted_data: Dict) -> Dict[str, any]:
        """
        Generate hierarchical Drools rules from extracted data (3 levels)

        :param extracted_data: Data extracted by Textract
        :return: Dictionary with 'level1_drl', 'level2_drl', 'level3_drl', and 'explanation' keys
        """
        try:
            result = self.hierarchical_chain.invoke({
                "extracted_data": json.dumps(extracted_data, indent=2)
            })

            # Parse LLM response to extract the three DRL files
            content = result.content

            # Extract Level 1 DRL
            level1_drl = self._extract_code_block(content, 'level1-drl') or \
                        self._extract_code_block(content, 'drl')  # Fallback

            # Extract Level 2 DRL
            level2_drl = self._extract_code_block(content, 'level2-drl')

            # Extract Level 3 DRL
            level3_drl = self._extract_code_block(content, 'level3-drl')

            # Extract explanation
            explanation = self._extract_explanation(content)

            # Fallback: If LLM didn't follow the format, use single-level generation
            if not level1_drl or not level2_drl or not level3_drl:
                print("⚠ LLM did not generate all 3 levels, falling back to single-level generation")
                single_result = self.generate_rules(extracted_data)

                # Split single DRL into 3 equal parts as fallback (not ideal but functional)
                drl_content = single_result.get('drl', '')
                return {
                    'level1_drl': drl_content,
                    'level2_drl': "// No Level 2 rules generated",
                    'level3_drl': "// No Level 3 rules generated",
                    'explanation': "Fallback: Generated single-level rules only",
                    'raw_response': content,
                    'hierarchical': False
                }

            return {
                'level1_drl': level1_drl,
                'level2_drl': level2_drl,
                'level3_drl': level3_drl,
                'explanation': explanation,
                'raw_response': content,
                'hierarchical': True
            }

        except Exception as e:
            print(f"Error generating hierarchical rules: {e}")
            return {
                'level1_drl': "// Error generating level 1 rules",
                'level2_drl': "// Error generating level 2 rules",
                'level3_drl': "// Error generating level 3 rules",
                'explanation': f"Error: {str(e)}",
                'raw_response': "",
                'hierarchical': False
            }

    def generate_template_drl(self, rule_category: str) -> str:
        """
        Generate template DRL for common rule categories

        :param rule_category: Category of rules (age_check, coverage_limit, etc.)
        :return: DRL template
        """
        templates = {
            "age_check": """package com.underwriting.rules;

// Declare types directly in DRL
declare Applicant
    name: String
    age: int
    occupation: String
end

declare Decision
    approved: boolean
    reason: String
    requiresManualReview: boolean
end

rule "Initialize Decision"
    when
        not Decision()
    then
        Decision decision = new Decision();
        decision.setApproved(true);
        decision.setReason("Initial evaluation");
        decision.setRequiresManualReview(false);
        insert(decision);
end

rule "Age Requirement Check"
    when
        $applicant : Applicant( age < 18 || age > 65 )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.setReason("Applicant age is outside acceptable range (18-65)");
        update($decision);
end""",

            "coverage_limit": """package com.underwriting.rules;

// Declare types directly in DRL
declare Policy
    policyType: String
    coverageAmount: double
    term: int
end

declare Decision
    approved: boolean
    reason: String
    requiresManualReview: boolean
end

rule "Initialize Decision"
    when
        not Decision()
    then
        Decision decision = new Decision();
        decision.setApproved(true);
        decision.setReason("Initial evaluation");
        decision.setRequiresManualReview(false);
        insert(decision);
end

rule "Coverage Limit Check"
    when
        $policy : Policy( coverageAmount > 500000 )
        $decision : Decision()
    then
        $decision.setRequiresManualReview(true);
        $decision.setReason("Coverage amount exceeds automatic approval threshold");
        update($decision);
end""",

            "risk_assessment": """package com.underwriting.rules;

// Declare types directly in DRL
declare Applicant
    name: String
    age: int
    occupation: String
end

declare RiskProfile
    riskScore: int
end

declare Decision
    approved: boolean
    reason: String
    requiresManualReview: boolean
    premiumMultiplier: double
end

rule "Initialize Decision"
    when
        not Decision()
    then
        Decision decision = new Decision();
        decision.setApproved(true);
        decision.setReason("Initial evaluation");
        decision.setRequiresManualReview(false);
        decision.setPremiumMultiplier(1.0);
        insert(decision);
end

rule "High Risk Assessment"
    when
        $applicant : Applicant()
        $risk : RiskProfile( riskScore > 80 )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.setReason("Risk score exceeds acceptable threshold");
        $decision.setPremiumMultiplier(1.5);
        update($decision);
end"""
        }

        return templates.get(rule_category, templates["age_check"])
