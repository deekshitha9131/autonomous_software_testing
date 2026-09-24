import json
data=json.load(open("verification_response.json"))
print("1. execution_status:", data.get("execution_status"))
print("2. failure_detected:", data.get("failure_detected"))
fa = data.get("failure_analysis", {})
print("3. failure_analysis summary:", fa.get("failure_summary"))
print("   failure_analysis root_cause:", fa.get("probable_root_cause"))
br = data.get("bug_report", {})
print("4. bug_report requirement:", br.get("requirement"))
rt = data.get("regression_test", {})
print("5. regression_test description:", rt.get("description"))
print("6. human_approval_required:", data.get("human_approval_required"))
errors = data.get("errors", [])
if errors:
    print("Runtime errors:", errors)
else:
    print("No runtime errors")
