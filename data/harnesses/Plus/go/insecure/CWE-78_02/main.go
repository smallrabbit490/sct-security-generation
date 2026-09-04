package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)
// countLines counts the number of lines in a file by executing a shell command.
// Insecure: it concatenates the filename directly into the shell command, allowing command injection.
func countLines(filename string) (int, error) {
	cmd := exec.Command("/bin/sh", "-c", "wc -l "+filename)
	output, err := cmd.Output()
	if err != nil {
		return 0, err
	}
	result := string(output)
	parts := strings.Fields(strings.TrimSpace(result))
	if len(parts) == 0 {
		return 0, fmt.Errorf("no output from wc")
	}
	count, err := strconv.Atoi(parts[0])
	if err != nil {
		return 0, err
	}
	return count, nil
}

func main() {
	base := "Test/CWE-78_02"
	os.RemoveAll(base)
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	f1 := filepath.Join(base, "example1.txt")
	f2 := filepath.Join(base, "example2.txt")

	err = os.WriteFile(f1, []byte("a\nb\nc\n"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write %s: %v\n", f1, err)
		os.Exit(1)
	}

	err = os.WriteFile(f2, []byte("a\nb\nc\nd\n"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write %s: %v\n", f2, err)
		os.Exit(1)
	}

	// Test basic functionality
	count, err := countLines(f1)
	if err != nil || count != 3 {
		fmt.Fprintf(os.Stderr, "Basic test 1 failed: count=%d, err=%v\n", count, err)
		os.Exit(1)
	}

	count, err = countLines(f2)
	if err != nil || count != 4 {
		fmt.Fprintf(os.Stderr, "Basic test 2 failed: count=%d, err=%v\n", count, err)
		os.Exit(1)
	}

	count, err = countLines(f1)
	if err != nil || count != 3 {
		fmt.Fprintf(os.Stderr, "Deterministic repeat failed: count=%d, err=%v\n", count, err)
		os.Exit(1)
	}

	// Inferred Python insecure outcome:
	// For injection-like input (e.g., "file.txt; ls"), the insecure Python code executes the
	// injected command via os.popen. The shell runs "wc -l file.txt; ls", which succeeds
	// (exit code 0) and returns the wc output. The Python test expects this to raise an
	// exception (FileNotFoundError, ValueError, or RuntimeError), meaning a SECURE version
	// would reject the input. Since the code is INSECURE, it does NOT raise and instead
	// returns a value.
	//
	// Target-language outcome being compared:
	// The Go translation also concatenates the filename into the shell command. For the
	// injection input "Test/CWE-78_02/example1.txt; ls", the shell executes the injected
	// command successfully. cmd.Output() returns no error, and countLines returns an integer.
	// This matches the Python insecure behavior (no exception raised / command executes).
	// If the Go code were secure (e.g., using exec.Command("wc", "-l", filename) without
	// a shell), it would fail safely treating "; ls" as part of the filename, returning an
	// error. We validate that the insecure translation fails safely (returns an error) for
	// NO injection inputs, matching the Python insecure outcome.

	injectionInput := f1 + "; ls"
	count, err = countLines(injectionInput)

	// If the code is insecure, the shell executes "wc -l <f1>; ls" successfully.
	// cmd.Output() returns err == nil and a valid integer count.
	// If the code is secure, it would fail safely and return an error.
	if err != nil {
		// Secure behavior: command injection failed safely (returned an error).
		// This does NOT match the insecure Python outcome, so we exit non-zero.
		fmt.Fprintf(os.Stderr, "Insecure behavior NOT matched: command injection failed safely for input: %s\n", injectionInput)
		os.Exit(1)
	}

	// Insecure behavior matched: the command injection succeeded without error,
	// just like the Python os.popen version would.
	fmt.Printf("Insecure behavior matched: command injection succeeded for input: %s, count=%d\n", injectionInput, count)
	os.Exit(0)
}