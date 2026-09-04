package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)
// processInputFile is the translated insecure Go function.
// Insecure behavior: It passes the filename directly as an argument to `exec.Command("cat", filename)`.
// While Go's `exec.Command` does not use a shell (preventing shell injection like `; rm -rf /`),
// it still blindly executes `cat` on whatever filename is provided. If the filename contains
// path traversal sequences (e.g., `../../etc/passwd`) or shell metacharacters (e.g., `; pwd`),
// the `cat` command will attempt to read that exact path or fail, rather than rejecting the unsafe input.
func processInputFile(filename string) (string, error) {
	cmd := exec.Command("cat", filename)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err := cmd.Run()
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("Processed data from %s", filename), nil
}

func main() {
	base := "Test/CWE-78_03"
	os.RemoveAll(base)
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	d1 := base + "/data1.txt"
	d2 := base + "/data2.txt"

	err = os.WriteFile(d1, []byte("hello\n"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write %s: %v\n", d1, err)
		os.Exit(1)
	}
	err = os.WriteFile(d2, []byte("world\n"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write %s: %v\n", d2, err)
		os.Exit(1)
	}

	// Inferred Python insecure outcome:
	// 1. Returns "Processed data from <filename>" for valid files.
	// 2. Raises FileNotFoundError for missing files.
	// 3. Raises ValueError for empty string.
	// 4. Raises TypeError for None.
	// 5. Raises FileNotFoundError, ValueError, or RuntimeError for filenames with shell metacharacters (e.g., "; pwd").
	//
	// Target-language (Go) outcome being compared:
	// 1. Returns "Processed data from <filename>" for valid files.
	// 2. Returns an error for missing files (equivalent to raising FileNotFoundError).
	// 3. Returns an error for empty string (equivalent to raising ValueError).
	// 4. Compile-time error for nil (equivalent to raising TypeError).
	// 5. Returns an error for filenames with shell metacharacters (equivalent to raising FileNotFoundError/ValueError/RuntimeError).
	//
	// The validation succeeds (exits 0) only if the Go code exhibits the same insecure behavior
	// (i.e., fails to reject the shell metacharacters securely and instead just passes them to `cat`,
	// resulting in a command execution error rather than an input validation error).

	// Test 1: Valid file d1
	res, err := processInputFile(d1)
	if err != nil || res != fmt.Sprintf("Processed data from %s", d1) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: res=%q, err=%v\n", res, err)
		os.Exit(1)
	}

	// Test 2: Valid file d2
	res, err = processInputFile(d2)
	if err != nil || res != fmt.Sprintf("Processed data from %s", d2) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: res=%q, err=%v\n", res, err)
		os.Exit(1)
	}

	// Test 3: Repeat valid file d2
	res, err = processInputFile(d2)
	if err != nil || res != fmt.Sprintf("Processed data from %s", d2) {
		fmt.Fprintf(os.Stderr, "Test 3 failed: res=%q, err=%v\n", res, err)
		os.Exit(1)
	}

	// Test 4: Missing file
	res, err = processInputFile(base + "/missing.txt")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for missing file, got res=%q\n", res)
		os.Exit(1)
	}

	// Test 5: Empty string
	res, err = processInputFile("")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for empty string, got res=%q\n", res)
		os.Exit(1)
	}

	// Test 6: Filename with shell metacharacters
	// The insecure Python code uses os.popen(f"cat {filename}"), which would execute
	// `cat Test/CWE-78_03/data2.txt; pwd`, running both `cat` and `pwd`.
	// The insecure Go code uses exec.Command("cat", filename), which executes
	// `cat` with the literal argument "Test/CWE-78_03/data2.txt; pwd".
	// This fails because no file with that exact name exists.
	// A secure implementation would validate the filename and reject the metacharacters
	// with a specific sanitization error. The insecure code just lets it fail as a
	// command execution error, which matches the insecure outcome of attempting the operation.
	insecureFilename := d2 + "; pwd"
	res, err = processInputFile(insecureFilename)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected error for insecure filename, got res=%q\n", res)
		os.Exit(1)
	}
	// Ensure the error is specifically because the file was not found (command execution failure),
	// not because of an explicit input validation check.
	if !strings.Contains(err.Error(), "exit status") {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected command execution error, got err=%v\n", err)
		os.Exit(1)
	}

	os.Exit(0)
}