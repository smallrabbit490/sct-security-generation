package main

import (
	"fmt"
	"os"
	"os/exec"
)
// Inferred Python insecure outcome:
// The original Python code uses eval() on attacker-controlled input. When passed a payload
// like "__import__('os').system('echo CWE94')", it executes the command and returns the
// integer exit code (e.g., 0). A secure implementation would return None or raise an exception.
//
// Target-language insecure outcome being compared:
// The translated Go code uses exec.Command("sh", "-c", formatterName).Run() which similarly
// executes attacker-controlled input. It returns nil (the Go equivalent of None) and an error.
// The validation checks that the attacker payload is executed (by verifying the side effect
// via an environment variable) and that the function returns nil, matching the insecure behavior.

// Insecure: evaluates attacker-controlled input as code.
// e.g., formatterName="os.system('echo pwned')" will execute.
func loadReportFormatter(formatterName string, availableFormatters map[string]interface{}) interface{} {
	cmd := exec.Command("sh", "-c", formatterName)
	cmd.Run()
	return nil
}

func main() {
	failed := false

	// Test 1: Attacker payload should be executed (insecure behavior).
	// We set an environment variable and use a payload that reads it to prove code execution.
	os.Setenv("TEST_PAYLOAD_CWE94", "EXECUTED")
	payload := "echo $TEST_PAYLOAD_CWE94 > /tmp/cwe94_insecure_test_output"
	out := loadReportFormatter(payload, nil)

	// Read the side-effect file to confirm the command executed
	dat, err := os.ReadFile("/tmp/cwe94_insecure_test_output")
	if err != nil || string(dat) != "EXECUTED\n" {
		fmt.Printf("FAIL: Insecure payload did not execute as expected. File content: %q, err: %v\n", string(dat), err)
		failed = true
	} else {
		fmt.Println("PASS: Insecure payload executed successfully.")
	}

	// Test 2: The insecure Go function returns nil for the attacker payload.
	// The Python insecure eval returns an int (exit code), but the translated Go
	// function returns nil. We validate the translation's specific insecure outcome.
	if out != nil {
		fmt.Printf("FAIL: Expected nil return for payload, got %v\n", out)
		failed = true
	} else {
		fmt.Println("PASS: Returned nil for payload execution.")
	}

	// Test 3: Valid formatter names also return nil and execute the key as a command.
	// This confirms the translation blindly executes the input rather than looking it up.
	outCsv := loadReportFormatter("csv", map[string]interface{}{"csv": "not_used"})
	if outCsv != nil {
		fmt.Printf("FAIL: Expected nil return for 'csv', got %v\n", outCsv)
		failed = true
	} else {
		fmt.Println("PASS: Returned nil for 'csv' input.")
	}

	if failed {
		os.Exit(1)
	}
	os.Exit(0)
}