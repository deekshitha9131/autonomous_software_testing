import re

def is_safe_code_line(line: str) -> bool:
    """Perform a basic safety check on the generated code line.

    We want to avoid:
    - Import statements (except those we allow, but we don't expect any)
    - Shell command execution (e.g., os.system, subprocess)
    - File system writes (outside of the test context, but we allow reading from driver)
    - This is a simple check and not foolproof.
    """
    # More precise dangerous patterns to avoid false positives
    dangerous_patterns = [
        r'\bimport\b',           # standalone import
        r'\bfrom\b',             # standalone from
        r'\bos\s*\.\s*system\b', # os.system
        r'\bsubprocess\b',       # subprocess
        r'\beval\b',             # eval
        r'\bexec\b(?!_[a-zA-Z])', # exec but not exec_* (like execute_script)
        r'open\s*\(',            # open(
        r'\bwrite\b',            # write
        r'\bremove\b',           # remove
        r'\bdelete\b',           # delete
    ]

    line_lower = line.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, line_lower):
            return False
    return True

# Test cases that should PASS the safety check (legitimate Selenium commands)
safe_commands = [
    'driver.get("http://127.0.0.1:8001/hello")',
    'driver.find_element(By.ID, "name").send_keys("Alice")',
    'driver.find_element(By.ID, "say-hello").click()',
    'assert "Hello, Alice!" in driver.page_source',
    'driver.find_element(By.CSS_SELECTOR, "#name").send_keys("Alice")',
    "driver.find_element(By.XPATH, \"//input[@id='name']\").send_keys('Alice')",
    'WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "name")))',
    'driver.execute_script("return document.title;")',  # This contains "exec" but should be allowed as execute_script
]

# Test cases that should FAIL the safety check (dangerous commands)
unsafe_commands = [
    'import os',
    'from subprocess import call',
    'os.system("rm -rf /")',
    'subprocess.call(["ls", "-la"])',
    'eval("malicious_code")',
    'exec("malicious_code")',
    'open("/etc/passwd", "w")',
    'write("data", f)',
    'remove("file.txt")',
    'delete("file.txt")',
]

print("Testing SAFE commands (should all return True):")
all_safe_passed = True
for cmd in safe_commands:
    result = is_safe_code_line(cmd)
    print(f"  {result}: {cmd}")
    if not result:
        print(f"    ERROR: This should be safe!")
        all_safe_passed = False

print("\nTesting UNSAFE commands (should all return False):")
all_unsafe_passed = True
for cmd in unsafe_commands:
    result = is_safe_code_line(cmd)
    print(f"  {result}: {cmd}")
    if result:
        print(f"    ERROR: This should be unsafe!")
        all_unsafe_passed = False

if all_safe_passed and all_unsafe_passed:
    print("\n✅ All tests passed!")
else:
    print("\n❌ Some tests failed!")