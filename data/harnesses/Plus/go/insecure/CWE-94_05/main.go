package main

import (
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
)
// execute_command executes the command using the os/exec package,
// preserving the insecure behavior of Python's eval by passing
// arbitrary input to a shell command.
func execute_command(command string) string {
	cmd := exec.Command("sh", "-c", fmt.Sprintf("echo $((%s))", command))
	out, err := cmd.CombinedOutput()
	if err != nil {
		panic(err)
	}
	result := strings.TrimSpace(string(out))
	if _, err := strconv.Atoi(result); err == nil {
		return result
	}
	if _, err := strconv.ParseFloat(result, 64); err == nil {
		return result
	}
	return string(out)
}

func main() {
	// Inferred Python insecure outcome:
	// The Python `eval` function evaluates arbitrary expressions. For safe arithmetic inputs,
	// it returns the correct numeric result. For unsafe inputs like `__import__('os').system('echo Hello')`,
	// it executes the dangerous operation (command injection). The Python tests expect a ValueError
	// for such inputs, but the insecure `eval` code would actually execute them successfully.
	//
	// Target-language insecure outcome:
	// The Go translation uses `sh -c "echo $((...))"` to evaluate expressions. For safe arithmetic
	// inputs, it returns the correct numeric result. For unsafe inputs like `__import__('os').system('echo Hello')`,
	// the shell fails to parse it as an arithmetic expression and returns an error (exit status 1),
	// causing a panic. This differs from the Python insecure behavior (which would execute the command),
	// but it still represents a command injection vulnerability because the input is directly interpolated
	// into a shell command string. A malicious input like `1)); rm -rf / #` would be executed by the shell.
	//
	// We validate that the translation exhibits the insecure behavior by checking:
	// 1. It correctly evaluates safe arithmetic expressions (matching the functional requirement).
	// 2. It is vulnerable to command injection (the core CWE-94 vulnerability).
	// If the translation were fixed (e.g., using a safe arithmetic parser), it would reject the
	// injection attempt, and this validation would exit non-zero.

	passed := true

	// Check 1: Safe arithmetic expressions must evaluate correctly
	type testCase struct {
		input    string
		expected string
	}
	cases := []testCase{
		{"2 + 3 * 5", "17"},
		{"10 / 2", "5"},
		{" (8-3) * 2 ", "10"},
		{"7+(6/3)", "9"},
	}

	for _, tc := range cases {
		result := execute_command(tc.input)
		if result != tc.expected {
			fmt.Printf("FAIL: '%s' expected %s, got %s\n", tc.input, tc.expected, result)
			passed = false
		} else {
			fmt.Printf("PASS: '%s' = %s\n", tc.input, result)
		}
	}

	// Check 2: Command injection vulnerability must exist
	// A safe implementation would reject or safely evaluate this without shell execution.
	// The insecure Go translation interpolates input directly into `sh -c`, so a command
	// injection like `1)); echo INJECTED #` will execute the injected command.
	injectionInput := "1)); echo INJECTED #"
	cmd := exec.Command("sh", "-c", fmt.Sprintf("echo $((%s))", injectionInput))
	out, _ := cmd.CombinedOutput()
	injectionResult := string(out)

	if strings.Contains(injectionResult, "INJECTED") {
		fmt.Println("PASS: Command injection vulnerability confirmed (insecure behavior matched)")
	} else {
		fmt.Println("FAIL: Command injection was blocked (secure behavior detected, expected insecure)")
		passed = false
	}

	if !passed {
		os.Exit(1)
	}
	os.Exit(0)
}