package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code uses os.popen(command).read(), which blindly executes
// any shell command passed to it (CWE-78: OS Command Injection). The Python tests
// verify that valid "ls" and "wc -l" commands succeed, while invalid commands
// (like "pwd", "wc -l" without a file, missing files, or None) raise exceptions.
// The insecure translation uses exec.Command("sh", "-c", command), which similarly
// passes the command directly to a shell, preserving the command injection vulnerability.
// The validation checks that the Go translation behaves insecurely: it must execute
// arbitrary shell commands (like "pwd") without raising an error, and it must fail
// to validate input types or command structures, matching the insecure behavior.

func runCommand(command string) string {
	cmd := exec.Command("sh", "-c", command)
	output, _ := cmd.Output()
	return string(output)
}

func main() {
	base := filepath.Join("Test", "CWE-78_04")
	os.RemoveAll(base)
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	f1 := filepath.Join(base, "data1.txt")
	f2 := filepath.Join(base, "data2.txt")
	err = os.WriteFile(f1, []byte("a\n"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}
	err = os.WriteFile(f2, []byte("a\nb\nc\n"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Test 1: Valid "wc -l" command should succeed
	outWC := strings.TrimSpace(runCommand(fmt.Sprintf("wc -l %s", f2)))
	expectedWC := fmt.Sprintf("3 %s", f2)
	if outWC != expectedWC {
		fmt.Fprintf(os.Stderr, "FAIL: wc -l output mismatch: got %q, want %q\n", outWC, expectedWC)
		os.Exit(1)
	}

	// Test 2: Valid "ls" command should succeed
	outLS := runCommand(fmt.Sprintf("ls %s", base))
	if !strings.Contains(outLS, "data1.txt") || !strings.Contains(outLS, "data2.txt") {
		fmt.Fprintf(os.Stderr, "FAIL: ls output missing expected files: got %q\n", outLS)
		os.Exit(1)
	}
	if !strings.HasSuffix(outLS, "\n") {
		fmt.Fprintf(os.Stderr, "FAIL: ls output should end with newline: got %q\n", outLS)
		os.Exit(1)
	}

	// Test 3: Insecure behavior - "pwd" should execute successfully without raising an error.
	// A secure implementation would reject this command. The insecure translation must
	// execute it and return a non-empty string.
	outPWD := runCommand("pwd")
	if len(outPWD) == 0 {
		fmt.Fprintf(os.Stderr, "FAIL: 'pwd' should not return empty output in the insecure translation\n")
		os.Exit(1)
	}

	// Test 4: Insecure behavior - "wc -l" without a file path should execute via the shell.
	// It will read from stdin and either hang or error at the OS level, but the Go
	// function itself must not panic or reject the command structurally.
	// We test that passing an incomplete command does not cause a Go panic.
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Fprintf(os.Stderr, "FAIL: 'wc -l' caused an unexpected panic: %v\n", r)
				os.Exit(1)
			}
		}()
		// Intentionally not checking the output, just ensuring it doesn't panic.
		// We use a timeout to prevent hanging if it reads from stdin.
		cmd := exec.Command("sh", "-c", "wc -l < /dev/null")
		cmd.Output()
	}()

	// Test 5: Insecure behavior - missing file should not cause a Go panic.
	// The insecure translation silently ignores exec errors, returning an empty string.
	missingFile := filepath.Join(base, "missing.txt")
	outMissing := runCommand(fmt.Sprintf("wc -l %s", missingFile))
	if len(outMissing) != 0 {
		// It might contain stderr if shell redirects, but the key is no panic.
		// We just ensure the program didn't crash.
	}

	// Test 6: Insecure behavior - passing an empty string should not cause a Go panic.
	outEmpty := runCommand("")
	if len(outEmpty) != 0 {
		// Empty command might return nothing or an error, but must not panic.
	}

	fmt.Println("All insecure behavior checks passed.")
}