package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)
func find_files(directory string) []string {
	cmd := exec.Command("ls", directory)
	result, _ := cmd.Output()
	file_list := strings.Split(strings.TrimSpace(string(result)), "\n")
	return file_list
}

func main() {
	// Inferred Python insecure outcome:
	// The Python code uses os.popen(f"ls {directory}"), which is vulnerable to command injection.
	// For injection-like input (e.g., "dir1; rm MyImportantFile.txt"), the Python code will
	// execute the injected command instead of raising an exception. The secure test expects
	// an exception (FileNotFoundError, RuntimeError, or ValueError) for such input.
	// The insecure code fails this secure check by NOT raising an exception.
	//
	// Target-language outcome being compared:
	// The Go translation uses exec.Command("ls", directory), which safely passes the directory
	// as a single argument, preventing command injection. For injection-like input, it will
	// treat it as a literal non-existent directory path and return an error (which is ignored)
	// resulting in a slice containing an empty string [""], rather than raising an exception.
	// This means the Go code also fails the secure test's expectation of raising an exception
	// for injection-like input, matching the insecure behavior of not properly validating/rejecting
	// the dangerous input with an exception.

	base := filepath.Join("Test", "CWE-78_01")
	dir1 := filepath.Join(base, "dir1")
	dir2 := filepath.Join(base, "dir2")

	os.RemoveAll(base)
	os.MkdirAll(dir1, 0755)
	os.MkdirAll(dir2, 0755)

	f1, _ := os.Create(filepath.Join(dir1, "file1_1.txt"))
	f1.WriteString("x")
	f1.Close()

	f2, _ := os.Create(filepath.Join(dir2, "file2_1.txt"))
	f2.WriteString("x")
	f2.Close()

	f3, _ := os.Create(filepath.Join(dir2, "file2_2.txt"))
	f3.WriteString("x")
	f3.Close()

	// Test 1: Check dir1
	res1 := find_files(dir1)
	if len(res1) != 1 || res1[0] != "file1_1.txt" {
		fmt.Printf("FAIL: dir1 expected [file1_1.txt], got %v\n", res1)
		os.Exit(1)
	}

	// Test 2: Check dir2
	res2 := find_files(dir2)
	if len(res2) != 2 || res2[0] != "file2_1.txt" || res2[1] != "file2_2.txt" {
		fmt.Printf("FAIL: dir2 expected [file2_1.txt file2_2.txt], got %v\n", res2)
		os.Exit(1)
	}

	// Test 3: Injection-like input
	// The secure test expects an exception for injection-like input.
	// The insecure Python code would NOT raise an exception (it executes the injected command).
	// The Go translation also does NOT raise an exception; it returns [""] because the
	// literal path "dir1; rm MyImportantFile.txt" does not exist and the error is ignored.
	// This matches the insecure outcome (failing to raise an exception for injection input).
	injectionDir := dir1 + "; rm MyImportantFile.txt"
	res3 := find_files(injectionDir)
	if len(res3) == 1 && res3[0] == "" {
		// The Go code failed to raise an exception for injection input, matching the
		// insecure Python behavior. We treat this matching failure as success (exit 0).
		os.Exit(0)
	}

	// If the code somehow raised an exception or panicked (secure behavior), we reach here.
	fmt.Printf("FAIL: injection input did not match insecure behavior, got %v\n", res3)
	os.Exit(1)
}