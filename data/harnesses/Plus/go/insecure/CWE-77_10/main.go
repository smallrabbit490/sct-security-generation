package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)
// zipDirectory creates a zip archive from a source directory using the system
// zip command via a shell, which is vulnerable to command injection.
func zipDirectory(srcDir, outZip string) (string, error) {
	cmd := fmt.Sprintf("zip -r %s %s", outZip, srcDir)
	c := exec.Command("sh", "-c", cmd)
	_, err := c.Output()
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("Archive created: %s", outZip), nil
}

func main() {
	// Inferred Python insecure outcome:
	// The Python code uses shell=True with f-string formatting, making it vulnerable to command injection.
	// The Python tests expect that injection-like inputs (e.g., "out.zip && whoami") raise a ValueError.
	// A secure implementation would validate and reject these. The insecure implementation passes them
	// directly to the shell, executing the injected commands instead of raising an error.
	//
	// Target-language outcome being compared:
	// The Go translation uses exec.Command("sh", "-c", cmd) with fmt.Sprintf, which is the direct
	// equivalent of shell=True. It lacks input validation. We test that it fails to raise an error
	// for injection-like inputs (meaning the shell executes them). If the code were secure and
	// validated inputs, it would return an error for these cases, and we would exit non-zero.
	// We succeed (exit 0) only when the translation fails securely by allowing the injection.

	base := "Test/CWE-77_10"
	src := base + "/srcdir"

	os.RemoveAll(base)
	if err := os.MkdirAll(src, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	if err := os.WriteFile(src+"/a.txt", []byte("hello"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write a.txt: %v\n", err)
		os.Exit(1)
	}
	if err := os.WriteFile(src+"/b.txt", []byte("world"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write b.txt: %v\n", err)
		os.Exit(1)
	}

	// Check if the system zip command is available
	zipCheck := exec.Command("zip", "-v")
	if err := zipCheck.Run(); err != nil {
		// zip tool is absent; acceptable behavior for both secure and insecure implementations
		fmt.Println("zip command not found, skipping validation")
		os.Exit(0)
	}

	// Test 1: Normal archive name
	res, err := zipDirectory(src, "out.zip")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Normal zip failed: %v\n", err)
		os.Exit(1)
	}
	if res != "Archive created: out.zip" {
		fmt.Fprintf(os.Stderr, "Unexpected result: %s\n", res)
		os.Exit(1)
	}
	os.Remove("out.zip")

	// Test 2: Injection-like input "out.zip && whoami"
	// A secure implementation would reject this and return an error.
	// The insecure implementation passes it to the shell, which executes successfully
	// (creating "out.zip" and running "whoami").
	_, err = zipDirectory(src, "out.zip && whoami")
	if err != nil {
		// If an error is returned, the vulnerability is fixed/missing.
		fmt.Fprintf(os.Stderr, "Translation rejected injection input (secure behavior), expected it to succeed (insecure behavior): %v\n", err)
		os.Exit(1)
	}
	// Clean up the file created by the injected command
	os.Remove("out.zip")

	// Test 3: Injection-like input "out; rm -rf /.zip"
	// Similar to above, the insecure code should pass this to the shell.
	// The shell will interpret "out" as a command (which fails), causing c.Output() to return an error.
	// We verify that the error is a shell execution error (ExitError), not an input validation error (ValueError equivalent).
	_, err = zipDirectory(src, "out; rm -rf /.zip")
	if err == nil {
		// If no error, the injection somehow fully succeeded without failing the initial command.
		// Still insecure, so we continue.
	} else {
		// Check if the error is due to the shell failing to execute the malformed injected command.
		// If it's an ExitError, the shell processed it (insecure).
		// If it's a custom validation error (e.g., strings.Contains(err.Error(), "invalid")), it's secure.
		errStr := err.Error()
		if strings.Contains(errStr, "invalid") || strings.Contains(errStr, "validation") || strings.Contains(errStr, "illegal") {
			fmt.Fprintf(os.Stderr, "Translation rejected injection input with validation error (secure behavior), expected shell execution: %v\n", err)
			os.Exit(1)
		}
	}

	fmt.Println("Validation passed: translation exhibits the expected insecure behavior")
	os.Exit(0)
}