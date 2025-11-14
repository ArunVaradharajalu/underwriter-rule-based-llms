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

        self.rule_generation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in insurance underwriting rules and Drools rule engine, specializing in multi-level dependency rules.

Given extracted policy data, generate executable Drools DRL (Drools Rule Language) rules that handle SEQUENTIAL EVALUATION where rules build upon previous outcomes.

IMPORTANT: Use 'declare' statements to define types directly in the DRL file. Do NOT import external Java classes.

=== MULTI-LEVEL DEPENDENCY PATTERNS ===

Many policies require STAGED EVALUATION where:
1. Early rules establish INTERMEDIATE FACTS (CreditTier, RiskCategory)
2. Later rules DEPEND on those facts to make decisions
3. Rules must execute IN ORDER using SALIENCE

The rules should follow this structure for MULTI-LEVEL policies:

```drl
package com.underwriting.rules;

// ============================================================================
// PART 1: DECLARE ALL TYPES (including intermediate facts for multi-level rules)
// ============================================================================

// Main input types
declare Applicant
    name: String
    age: int
    creditScore: int
    health: String  // "excellent", "good", "fair"
    annualIncome: double
    debtToIncomeRatio: double
    smoking: boolean
    occupation: String
    occupationType: String  // "standard", "hazardous"
end

declare Policy
    policyType: String
    coverageAmount: double
    term: int
end

// Intermediate fact types for multi-level dependencies
declare CreditTier
    tier: String  // "A" (750+), "B" (700-749), "C" (600-699)
end

declare AgeBracket
    bracket: String  // "young" (18-35), "middle" (36-50), "senior" (51-65)
end

declare RiskPoints
    factor: String  // "credit", "age", "health", "smoking", "dti", "occupation"
    points: int
end

declare RiskCategory
    category: int  // 1 (low) through 5 (very high)
    totalPoints: int
end

declare ApprovalStatus
    stage: String  // "primary", "financial", "risk", "final"
    passed: boolean
    reason: String
end

// Final decision type
declare Decision
    approved: boolean
    reasons: java.util.List
    requiresManualReview: boolean
    premiumMultiplier: double
    riskCategory: int
end

// ============================================================================
// PART 2: INITIALIZATION RULES (Highest Salience)
// ============================================================================

rule "Initialize Decision"
    salience 10000
    when
        not Decision()
    then
        Decision decision = new Decision();
        decision.setApproved(true);
        decision.setReasons(new java.util.ArrayList());
        decision.setRequiresManualReview(false);
        decision.setPremiumMultiplier(1.0);
        decision.setRiskCategory(0);
        insert(decision);
end

// ============================================================================
// PART 3: STAGE 1 - ESTABLISH CLASSIFICATIONS (Salience 9000-9999)
// ============================================================================

rule "Establish Credit Tier A"
    salience 9000
    when
        $applicant : Applicant( creditScore >= 750 )
        not CreditTier()
    then
        CreditTier ct = new CreditTier();
        ct.setTier("A");
        insert(ct);
end

rule "Establish Credit Tier B"
    salience 9000
    when
        $applicant : Applicant( creditScore >= 700, creditScore < 750 )
        not CreditTier()
    then
        CreditTier ct = new CreditTier();
        ct.setTier("B");
        insert(ct);
end

rule "Establish Credit Tier C"
    salience 9000
    when
        $applicant : Applicant( creditScore >= 600, creditScore < 700 )
        not CreditTier()
    then
        CreditTier ct = new CreditTier();
        ct.setTier("C");
        insert(ct);
end

rule "Establish Age Bracket - Young"
    salience 9000
    when
        $applicant : Applicant( age >= 18, age <= 35 )
        not AgeBracket()
    then
        AgeBracket ab = new AgeBracket();
        ab.setBracket("young");
        insert(ab);
end

rule "Establish Age Bracket - Middle"
    salience 9000
    when
        $applicant : Applicant( age >= 36, age <= 50 )
        not AgeBracket()
    then
        AgeBracket ab = new AgeBracket();
        ab.setBracket("middle");
        insert(ab);
end

rule "Establish Age Bracket - Senior"
    salience 9000
    when
        $applicant : Applicant( age >= 51, age <= 65 )
        not AgeBracket()
    then
        AgeBracket ab = new AgeBracket();
        ab.setBracket("senior");
        insert(ab);
end

// ============================================================================
// PART 4: STAGE 1 - PRIMARY ELIGIBILITY CHECKS (Salience 8000-8999)
// ============================================================================

rule "Reject - Age Out of Range"
    salience 8500
    when
        $applicant : Applicant( age < 18 || age > 65 )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.getReasons().add("Applicant age must be between 18 and 65");
        update($decision);
end

rule "Reject - Credit Score Too Low"
    salience 8500
    when
        $applicant : Applicant( creditScore < 600 )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.getReasons().add("Minimum credit score of 600 required");
        update($decision);
end

// ============================================================================
// PART 5: STAGE 2 - COMPOUND CONDITION CHECKS (Salience 7000-7999)
// These rules depend on CreditTier being established first
// ============================================================================

rule "Reject - Tier C with Fair Health"
    salience 7500
    when
        CreditTier( tier == "C" )
        $applicant : Applicant( health == "fair" )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.getReasons().add("Tier C applicants with fair health are not eligible");
        update($decision);
end

rule "Income Check - Tier A Excellent Health"
    salience 7000
    when
        CreditTier( tier == "A" )
        $applicant : Applicant( health == "excellent", annualIncome < 20000 )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.getReasons().add("Tier A with excellent health requires minimum income $20,000");
        update($decision);
end

rule "Income Check - Tier A Good Health"
    salience 7000
    when
        CreditTier( tier == "A" )
        $applicant : Applicant( health == "good", annualIncome < 25000 )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.getReasons().add("Tier A with good health requires minimum income $25,000");
        update($decision);
end

rule "Coverage Limit Check - Tier A Excellent Health"
    salience 7000
    when
        CreditTier( tier == "A" )
        $applicant : Applicant( health == "excellent", $income : annualIncome )
        $policy : Policy( coverageAmount > ($income * 12) )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.getReasons().add("Tier A with excellent health limited to 12x annual income");
        update($decision);
end

// ============================================================================
// PART 6: STAGE 3 - RISK POINT CALCULATION (Salience 6000-6999)
// ============================================================================

rule "Calculate Risk Points - Credit Tier"
    salience 6000
    when
        CreditTier( $tier : tier )
        not RiskPoints( factor == "credit" )
    then
        int points = "A".equals($tier) ? 0 : ("B".equals($tier) ? 2 : 5);
        RiskPoints rp = new RiskPoints();
        rp.setFactor("credit");
        rp.setPoints(points);
        insert(rp);
end

rule "Calculate Risk Points - Age"
    salience 6000
    when
        $applicant : Applicant( $age : age )
        not RiskPoints( factor == "age" )
    then
        int points = ($age <= 30) ? 0 : (($age <= 40) ? 1 : (($age <= 50) ? 3 : (($age <= 60) ? 5 : 8)));
        RiskPoints rp = new RiskPoints();
        rp.setFactor("age");
        rp.setPoints(points);
        insert(rp);
end

rule "Calculate Risk Points - Health"
    salience 6000
    when
        $applicant : Applicant( $health : health )
        not RiskPoints( factor == "health" )
    then
        int points = "excellent".equals($health) ? 0 : ("good".equals($health) ? 2 : 6);
        RiskPoints rp = new RiskPoints();
        rp.setFactor("health");
        rp.setPoints(points);
        insert(rp);
end

rule "Calculate Risk Points - Smoking"
    salience 6000
    when
        $applicant : Applicant( $smoking : smoking )
        not RiskPoints( factor == "smoking" )
    then
        int points = $smoking ? 5 : 0;
        RiskPoints rp = new RiskPoints();
        rp.setFactor("smoking");
        rp.setPoints(points);
        insert(rp);
end

// ============================================================================
// PART 7: STAGE 4 - RISK CATEGORY ASSIGNMENT (Salience 5000-5999)
// ============================================================================

rule "Calculate Total Risk Points and Assign Category"
    salience 5000
    when
        not RiskCategory()
        accumulate(
            RiskPoints( $p : points );
            $total : sum($p)
        )
    then
        int total = $total.intValue();
        int category = (total <= 5) ? 1 : ((total <= 10) ? 2 : ((total <= 15) ? 3 : ((total <= 20) ? 4 : 5)));
        RiskCategory rc = new RiskCategory();
        rc.setCategory(category);
        rc.setTotalPoints(total);
        insert(rc);
end

// ============================================================================
// PART 8: STAGE 5 - RISK-BASED DECISIONS (Salience 4000-4999)
// ============================================================================

rule "Risk Category 3+ Requires Manual Review"
    salience 4000
    when
        RiskCategory( category >= 3 )
        $decision : Decision()
    then
        $decision.setRequiresManualReview(true);
        update($decision);
end

rule "Set Premium Multiplier by Risk Category"
    salience 4000
    when
        RiskCategory( $cat : category )
        $decision : Decision()
    then
        double multiplier = ($cat == 1) ? 1.0 : (($cat == 2) ? 1.3 : (($cat == 3) ? 1.7 : (($cat == 4) ? 2.2 : 2.5)));
        $decision.setPremiumMultiplier(multiplier);
        $decision.setRiskCategory($cat);
        update($decision);
end

// ============================================================================
// PART 9: FINAL DECISION RULES (Salience 1000-1999)
// ============================================================================

rule "Final Approval Check"
    salience 1000
    when
        $decision : Decision( approved == true, requiresManualReview == false )
    then
        // All checks passed - automatic approval
        System.out.println("Application APPROVED");
end
```

GUIDELINES FOR MULTI-LEVEL RULES:

1. **ALWAYS use 'declare' statements** to define Applicant, Policy, Decision, and ALL intermediate types (CreditTier, RiskCategory, etc.)
2. **Do NOT use import statements** for model classes
3. **CRITICAL: Use setter-based initialization for declared types**, NOT constructors:
   - CORRECT: `CreditTier ct = new CreditTier(); ct.setTier("A"); insert(ct);`
   - WRONG: `insert(new CreditTier("A"));` (constructors don't work with declared types)
4. **Use SALIENCE to control execution order**:
   - 10000: Initialization
   - 9000-9999: Establish classifications (CreditTier, AgeBracket)
   - 8000-8999: Primary eligibility checks (age, credit minimum)
   - 7000-7999: Compound condition checks (depend on CreditTier + Health)
   - 6000-6999: Risk point calculation
   - 5000-5999: Risk category assignment
   - 4000-4999: Risk-based decisions
   - 1000-1999: Final decisions
5. **Create separate rules for EACH compound condition**:
   - One rule for "Tier A + Excellent Health"
   - One rule for "Tier A + Good Health"
   - One rule for "Tier A + Fair Health"
   - (repeat for Tier B and Tier C)
6. **Use intermediate fact types** for classifications that are used in later rules
7. **Always check "not <FactType>()" before inserting** to prevent duplicates
8. **Use proper getter/setter methods**: setApproved(), getReasons().add("reason")
9. **For rejection rules, use $decision.getReasons().add()** to accumulate ALL rejection reasons
10. **NEVER use setReason() or setReasons()** in rejection rules - always use getReasons().add()
11. **When comparing fields from different objects**, use variable binding:
    - CORRECT: `$applicant : Applicant( $income : annualIncome )  $policy : Policy( coverageAmount > ($income * 10) )`
    - WRONG: `$applicant : Applicant( annualIncome * 10 < coverageAmount )`
12. **For point-based systems**, use setter-based initialization for RiskPoints:
    - CORRECT: `RiskPoints rp = new RiskPoints(); rp.setFactor("credit"); rp.setPoints(points); insert(rp);`
13. **Use 'not' checks** to ensure rules fire only once: `when not CreditTier() then ...`
14. **Add comments** to mark each stage clearly
15. **Handle special rejection rules** early (high salience) to short-circuit evaluation
16. **Create clear, specific rule names** based on the extracted data (e.g., "Income Check - Tier A Excellent Health")
17. **Make rules executable and testable** - ensure all syntax is valid Drools DRL
18. **Add section comments** to organize rules by stage/purpose

SPECIAL HANDLING FOR EXTRACTED DATA:

If extracted data contains:
- **dependency_stages**: Use this to determine salience ranges and intermediate fact types
- **intermediate_facts**: Declare these as Drools types (e.g., CreditTier, RiskCategory)
- **special_rejection_rules**: Generate high-salience rules for these compound rejections
- **Matrix data** (e.g., "Tier A + Excellent Health" combinations): Generate one rule per cell

Return your response with:
1. Complete DRL rules in ```drl code blocks (including ALL declare statements for intermediate facts)
2. Brief explanation of the rules organized by stage
3. List of intermediate facts that later rules depend on

DO NOT generate decision tables - only generate DRL rules."""),
            ("user", """Extracted policy data:

{extracted_data}

Generate complete, self-contained Drools DRL rules with 'declare' statements for all types.""")
        ])

        self.chain = self.rule_generation_prompt | self.llm

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
