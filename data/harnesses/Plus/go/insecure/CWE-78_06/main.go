package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)
func listFiles(directory string) string {
	command := fmt.Sprintf("ls %s", directory)
	out, err := exec.Command("sh", "-c", command).Output()
	if err != nil {
		panic(err)
	}
	return string(out)
}

func main() {
	baseDir := "Test/CWE-78_06"

	// Clean up and create the test directory
	os.RemoveAll(baseDir)
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Create dummy files
	file, err := os.Create(baseDir + "/doc.txt")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}
	file.Close()

	file, err = os.Create(baseDir + "/image.png")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}
	file.Close()

	// --- Inferred Python insecure outcome ---
	// The Python code uses `subprocess.getoutput(f"ls {directory}")`, which is vulnerable to command injection.
	// For malicious inputs like "; rm -rf / #" or "&& echo hacked", the insecure Python code will
	// successfully execute the injected shell commands and return their output (e.g., "hacked") without raising an exception.
	// The Python tests assert that these malicious inputs *should* raise an exception (FileNotFoundError, ValueError, RuntimeError),
	// meaning the secure version must reject them. Since we are validating the *insecure* translation,
	// we expect it to FAIL this secure check by NOT raising an exception and returning the injected command's output.
	// For a non-existent path, the insecure Python code will output an error string to stdout (which it returns)
	// and `subprocess.getoutput` will NOT raise an exception, failing the secure test that expects FileNotFoundError.
	// For None, Python raises TypeError before subprocess, which matches the secure test.

	// --- Target-language outcome being compared ---
	// The Go translation uses `exec.Command("sh", "-c", fmt.Sprintf("ls %s", directory)).Output()`.
	// 1. For "; rm -rf / #", it executes the injected command. If the command succeeds (or fails silently),
	//    it might not panic, thus failing the secure check. If it panics due to a non-zero exit code,
	//    it behaves differently than the insecure Python (which returns output). We check that it fails the secure test.
	// 2. For "&& echo hacked", it executes `ls && echo hacked`, returning "hacked" in the output without panicking,
	//    directly matching the insecure Python behavior and failing the secure check.
	// 3. For "/this/path/does/not/exist", `ls` fails, `Output()` returns an error, and the Go code panics.
	//    The insecure Python code would NOT panic/raise here. This is a mismatch in insecure behavior,
	//    but the primary vulnerability (command injection) is confirmed by the "&& echo hacked" test.
	// 4. For empty string "", Go's `ls ` executes successfully, returning the current directory's listing,
	//    failing the secure check (which expects an error), matching the insecure Python outcome.

	// Test 1: Valid directory should work
	result := listFiles(baseDir)
	if !strings.Contains(result, "doc.txt") || !strings.Contains(result, "image.png") {
		fmt.Fprintf(os.Stderr, "FAIL: Expected doc.txt and image.png in output, got: %s\n", result)
		os.Exit(1)
	}

	// Test 2: Command injection with "&& echo hacked"
	// Insecure Python outcome: Returns output containing "hacked", no exception.
	// Insecure Go outcome: Returns output containing "hacked", no panic.
	// Secure expectation: Should raise an exception/panic.
	injectedResult := listFiles("&& echo hacked")
	if strings.Contains(injectedResult, "hacked") {
		// The insecure code successfully executed the injected command and returned its output,
		// failing the secure check. This is the expected insecure behavior.
	} else {
		// If it didn't contain "hacked", it might have panicked (caught by recovery below)
		// or failed to inject. If it panicked, it passed the secure check, so the validation must fail.
		fmt.Fprintf(os.Stderr, "FAIL: Command injection did not produce 'hacked' output. Code might be secure or injection failed unexpectedly. Got: %s\n", injectedResult)
		os.Exit(1)
	}

	// Test 3: Empty string injection
	// Insecure Python outcome: `ls ` executes successfully, returns current directory listing, no exception.
	// Insecure Go outcome: `ls ` executes successfully, returns current directory listing, no panic.
	// Secure expectation: Should raise an exception/panic.
	emptyResult := listFiles("")
	if len(emptyResult) > 0 {
		// The insecure code executed `ls ` and returned output, failing the secure check.
	} else {
		fmt.Fprintf(os.Stderr, "FAIL: Empty string injection did not produce output. Code might be secure.\n")
		os.Exit(1)
	}

	fmt.Println("Validation passed: Insecure behavior confirmed.")
}