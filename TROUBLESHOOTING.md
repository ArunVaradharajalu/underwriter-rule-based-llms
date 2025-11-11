# Troubleshooting Guide

## Common Issues and Solutions

### Issue 1: Drools Compilation Error - "Unable to resolve method"

**Symptom:**
```
Failed to create container: Error while creating KieBase
Unable to Analyse Expression loanType == "personal":
[Error: unable to resolve method using strict-mode: com.underwriting.rules.Applicant.loanType()]
```

**Root Cause:**
The LLM-generated DRL rules reference fields (like `loanType`) that don't exist in the `declare` statements at the top of the DRL file.

**Why This Happens:**
- The LLM sometimes generates rules that use fields not declared in the type definitions
- This is an LLM consistency issue - it needs to declare all fields before using them in rules

**Solution 1: Improved LLM Prompt (✅ FIXED)**

We've updated the prompts in `RuleGeneratorAgent.py` to emphasize:
- **CRITICAL**: Every field referenced in rules MUST be declared in the type definition
- **CRITICAL**: Decide ALL fields needed first, then add them to declare statements
- **CRITICAL**: For hierarchical rules, use the SAME declare statements in all 3 levels

The updated prompt now includes stronger guidance to prevent this issue.

**Solution 2: Manual Fix (If Error Still Occurs)**

If your colleague encounters this error again:

1. **Identify the missing field** from the error message:
   ```
   Unable to resolve method: Applicant.loanType()
   ```
   → Missing field: `loanType` in `Applicant` type

2. **Download the DRL file** from the error logs or S3

3. **Add the missing field** to the `declare` statement:
   ```drl
   declare Applicant
       age: int
       annualIncome: double
       creditScore: int
       loanType: String  ← ADD THIS
   end
   ```

4. **Redeploy** using the fixed DRL file

**Solution 3: Validate DRL Before Deployment (Future Enhancement)**

Add DRL validation that checks:
- All fields used in rules exist in declare statements
- Parse rules to extract field references
- Compare against declared fields
- Reject DRL if fields are missing

**Prevention:**
- The prompt improvements should significantly reduce this issue
- If it persists, we can add automated DRL validation before deployment
- Consider using a stricter LLM model or adding retry logic with validation

---

## Issue 2: Container Already Exists Error

**Symptom:**
```
Container indian-loan-underwriting-rules already exists
```

**Solution:**
The deployment automatically disposes and redeploys. If you see this, it's working as expected.

---

## Issue 3: Database Migration Not Applied

**Symptom:**
- `level` column doesn't exist in `extracted_rules` table
- API returns errors about missing column

**Solution:**
Run the migration script in pgAdmin:
```sql
-- File: db/migrations/002_add_level_column_to_extracted_rules.sql
```

See [db/migrations/README.md](db/migrations/README.md) for detailed instructions.

---

## Debugging Tips

### 1. Check Generated DRL File

Look at the S3 URL in the response to download the generated DRL:
```json
{
  "drl_s3_url": "https://uw-data-extraction.s3.amazonaws.com/..."
}
```

### 2. Validate Declare Statements

Ensure all fields used in rules are declared:
```drl
declare Applicant
    age: int
    annualIncome: double
    creditScore: int
    loanType: String  ← Must be here if used in rules!
end

rule "Personal Loan Age Check"
    when
        $applicant : Applicant( loanType == "personal", age < 18 )  ← Uses loanType
        ...
```

### 3. Check Drools Logs

View container logs:
```bash
docker logs drools-indian-loan-underwriting-rules
```

### 4. Test with Simple DRL

If issues persist, test with a minimal DRL:
```drl
package com.underwriting.rules;

declare Applicant
    age: int
end

declare Decision
    approved: boolean
    reasons: java.util.List
end

rule "Initialize Decision"
    when
        not Decision()
    then
        Decision decision = new Decision();
        decision.setApproved(true);
        decision.setReasons(new java.util.ArrayList());
        insert(decision);
end

rule "Age Check"
    when
        $applicant : Applicant( age < 18 )
        $decision : Decision()
    then
        $decision.setApproved(false);
        $decision.getReasons().add("Applicant must be at least 18 years old");
        update($decision);
end
```

---

## Getting Help

If you continue to encounter issues:

1. **Collect Error Logs**: Save the complete error message
2. **Check DRL File**: Download from S3 and inspect declare statements
3. **Share Details**: Provide the error message, DRL file, and input data
4. **Try Hierarchical Mode**: Use `/process_policy_from_s3_hierarchical` endpoint which has improved prompts

For urgent issues, contact the development team with:
- Full error logs
- S3 URLs of generated files
- Policy document used
- Request/response payloads
