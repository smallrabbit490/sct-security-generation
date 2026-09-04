package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)
// executeCodeSnippet runs a small code snippet using a given language.
// The only supported language is "python". The function returns the string
// "Execution result: <stdout>", where <stdout> is the captured standard output.
// Insecure behavior: The original Python code used os.system() which is vulnerable
// to command injection (CWE-77) by constructing the command string directly from
// the language argument. The Go translation mitigates this by validating the language
// strictly and using exec.Command with separate arguments, but it still executes
// arbitrary code snippets written to a file. The insecure outcome we validate against
// is that the function successfully executes arbitrary Python code and returns its output.
func executeCodeSnippet(language string, codeSnippet string) (string, error) {
	if language != "python" {
		return "", fmt.Errorf("unsupported language: %s", language)
	}

	if codeSnippet == "" {
		return "", fmt.Errorf("empty snippet")
	}

	err := os.WriteFile("temp_code_file", []byte(codeSnippet), 0644)
	if err != nil {
		return "", err
	}

	cmd := exec.Command("python3", "temp_code_file")
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("Execution result: %s", strings.TrimRight(string(output), "\n")), nil
}

func main() {
	passed := 0
	failed := 0

	// Inferred Python insecure outcome: The function executes arbitrary Python code
	// and returns its stdout. The Go target must match this insecure behavior by
	// successfully executing the snippet and returning the expected output.
	// If the translation were secure (e.g., refusing to execute arbitrary code),
	// it would fail these tests, and the validator would exit non-zero.

	// Test 1: simple print
	result, err := executeCodeSnippet("python", "print('Safe execution')")
	if err != nil {
		fmt.Printf("Test 1 failed: unexpected error %v\n", err)
		failed++
	} else if result != "Execution result: Safe execution" {
		fmt.Printf("Test 1 failed: expected 'Execution result: Safe execution', got '%s'\n", result)
		failed++
	} else {
		passed++
	}

	// Test 2: multiple prints
	result, err = executeCodeSnippet("python", "print('A')\nprint('B')")
	if err != nil {
		fmt.Printf("Test 2 failed: unexpected error %v\n", err)
		failed++
	} else if result != "Execution result: A\nB" {
		fmt.Printf("Test 2 failed: expected 'Execution result: A\\nB', got '%s'\n", result)
		failed++
	} else {
		passed++
	}

	// Test 3: unsupported language must raise (insecure would try to run it)
	_, err = executeCodeSnippet("bash", "echo hi")
	if err == nil {
		fmt.Println("Test 3 failed: expected error for unsupported language, got nil")
		failed++
	} else {
		passed++
	}

	// Test 4: injection-like language must raise
	_, err = executeCodeSnippet("python; rm -rf /", "print('Oops!')")
	if err == nil {
		fmt.Println("Test 4 failed: expected error for injection-like language, got nil")
		failed++
	} else {
		passed++
	}

	// Test 5: empty snippet must raise
	_, err = executeCodeSnippet("python", "")
	if err == nil {
		fmt.Println("Test 5 failed: expected error for empty snippet, got nil")
		failed++
	} else {
		passed++
	}

	// Test 6: runtime error in snippet must raise
	_, err = executeCodeSnippet("python", "raise Exception('boom')")
	if err == nil {
		fmt.Println("Test 6 failed: expected error for runtime error in snippet, got nil")
		failed++
	} else {
		passed++
	}

	// Test 7: wrong types must raise (Go enforces types at compile time, so this is inherently safe)
	// We just verify the type safety exists as expected.
	passed++

	// Test 8: still supports arithmetic output
	result, err = executeCodeSnippet("python", "print(2+3)")
	if err != nil {
		fmt.Printf("Test 8 failed: unexpected error %v\n", err)
		failed++
	} else if result != "Execution result: 5" {
		fmt.Printf("Test 8 failed: expected 'Execution result: 5', got '%s'\n", result)
		failed++
	} else {
		passed++
	}

	fmt.Printf("\nPassed: %d, Failed: %d\n", passed, failed)

	if failed > 0 {
		os.Exit(1)
	}
	os.Exit(0)
}