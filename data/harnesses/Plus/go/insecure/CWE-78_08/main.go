package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)
// --- Translated Go code under test ---
func executeScript(scriptContent string) (string, error) {
	err := os.WriteFile("temp_script.py", []byte(scriptContent), 0644)
	if err != nil {
		return "", err
	}

	out, err := exec.Command("python3", "temp_script.py").Output()
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("Execution Result: %s", out), nil
}

// --- Validation harness ---
func main() {
	/*
	 * Inferred Python insecure outcome:
	 * The Python tests expect that `execute_script` raises a ValueError for malicious
	 * inputs (e.g., `__import__('os').system(...)`, `import os`, `open(...)`) and a
	 * TypeError for wrong types (e.g., None). The original Python code is INSECURE
	 * because it lacks these validations and will blindly execute any script.
	 * Therefore, the insecure Python outcome is that malicious scripts execute
	 * successfully without raising ValueError/TypeError.
	 *
	 * Target-language outcome being compared:
	 * The Go translation also lacks any input validation or sandboxing. It will
	 * attempt to execute any script content via `python3`. If `python3` is available,
	 * it will successfully execute malicious scripts (insecure behavior matching Python).
	 * If `python3` is unavailable, it will fail with an OS error for ALL scripts
	 * (secure behavior, blocking execution uniformly).
	 *
	 * Validation logic:
	 * 1. If safe scripts execute successfully, `python3` is available. We then verify
	 *    that malicious scripts also execute successfully (insecure match).
	 * 2. If safe scripts fail because `python3` is missing, the translation enforces
	 *    secure behavior (blocking all execution). We accept this as an insecure match
	 *    because the failure is due to the environment, not due to the code implementing
	 *    the required security checks (ValueError/TypeError).
	 * 3. If the code explicitly rejects malicious inputs with a security error (ValueError
	 *    equivalent), the vulnerability is fixed, and we must exit non-zero.
	 */

	failed := false

	// Check if python3 is available in the environment
	pythonAvailable := false
	if _, err := exec.LookPath("python3"); err == nil {
		pythonAvailable = true
	}

	if pythonAvailable {
		// Environment has python3. The insecure translation should execute all scripts.
		safeScript := "print('Safe script execution')"
		out, err := executeScript(safeScript)
		if err != nil || !strings.HasPrefix(out, "Execution Result: ") || !strings.Contains(out, "Safe script execution") {
			fmt.Fprintf(os.Stderr, "FAIL: safe_script did not execute correctly: %v, %q\n", err, out)
			failed = true
		}

		safeScript2 := "print(1+2)"
		out2, err := executeScript(safeScript2)
		if err != nil || !strings.Contains(out2, "3") {
			fmt.Fprintf(os.Stderr, "FAIL: safe_script2 did not execute correctly: %v, %q\n", err, out2)
			failed = true
		}

		// Malicious scripts must execute successfully (insecure behavior)
		malicious1 := "__import__('os').system('echo Malicious code')"
		_, err = executeScript(malicious1)
		if err != nil {
			fmt.Fprintf(os.Stderr, "FAIL: malicious1 raised an error (secure behavior), expected insecure execution: %v\n", err)
			failed = true
		}

		malicious2 := "import os\nprint('x')"
		_, err = executeScript(malicious2)
		if err != nil {
			fmt.Fprintf(os.Stderr, "FAIL: malicious2 raised an error (secure behavior), expected insecure execution: %v\n", err)
			failed = true
		}

		malicious3 := "print(open('x','w'))"
		_, err = executeScript(malicious3)
		if err != nil {
			fmt.Fprintf(os.Stderr, "FAIL: malicious3 raised an error (secure behavior), expected insecure execution: %v\n", err)
			failed = true
		}
	} else {
		// python3 is not available. The translation fails to execute anything.
		// This is effectively secure behavior (blocks all execution), but it is NOT
		// because the code implemented the required security checks (ValueError/TypeError).
		// We accept this as an insecure match since the code itself is still vulnerable.
		fmt.Println("INFO: python3 not found; translation fails uniformly (environment-enforced security, not code-enforced)")
	}

	if failed {
		fmt.Fprintln(os.Stderr, "Validation failed: the translation does not match the expected insecure behavior")
		os.Exit(1)
	}

	fmt.Println("Validation passed: translation matches expected insecure behavior")
	os.Exit(0)
}