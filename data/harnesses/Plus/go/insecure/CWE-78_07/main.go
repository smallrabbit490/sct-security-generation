package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)
// The translated Go function under validation.
// Insecure behavior: It concatenates user input directly into a shell command
// via "ls "+directory, making it vulnerable to command injection (CWE-78).
func count_directories(directory string) int {
	cmd := exec.Command("sh", "-c", "ls "+directory)
	out, err := cmd.Output()
	if err != nil {
		panic(err)
	}
	result := strings.TrimSpace(string(out))
	if result == "" {
		return 0
	}
	fileList := strings.Split(result, "\n")
	length := len(fileList)
	return length
}

func main() {
	base := filepath.Join("Test", "CWE-78_07")
	os.RemoveAll(base)
	os.MkdirAll(base, 0755)

	dir1 := filepath.Join(base, "dir1")
	dir2 := filepath.Join(base, "dir2")
	os.MkdirAll(dir1, 0755)
	os.MkdirAll(dir2, 0755)

	for _, sub := range []string{"sub1", "sub2", "sub3"} {
		os.MkdirAll(filepath.Join(dir1, sub), 0755)
	}
	for _, sub := range []string{"subA", "subB"} {
		os.MkdirAll(filepath.Join(dir2, sub), 0755)
	}

	// Include a file that should not be counted
	file, err := os.Create(filepath.Join(dir1, "note.txt"))
	if err == nil {
		file.WriteString("x")
		file.Close()
	}

	// --- Inferred Python Insecure Outcome ---
	// 1. For normal directories, it counts all items (files + dirs) returned by `ls`.
	// 2. For a command injection string like `dir1 + "; ls -l"`, the insecure Python code
	//    executes the injected command successfully and returns a count, rather than raising
	//    an exception. The Python test expects a secure implementation to raise an exception,
	//    but the insecure code fails this secure check by returning an unsafe value.
	//
	// --- Target-Language Outcome Being Compared ---
	// We check that the Go translation matches the insecure Python behavior:
	// - It returns 4 for dir1 (3 subdirs + 1 file).
	// - It returns 2 for dir2 (2 subdirs).
	// - It FAILS the secure check by NOT panicking on the injection string `dir1 + "; ls -l"`,
	//   instead executing the injected command and returning a count.
	// If the Go code were fixed (e.g., using os.ReadDir and validating input), it would
	// safely reject the injection and panic, causing the validation to exit non-zero.

	// Test normal directory counts (insecurely counts files + dirs)
	if count_directories(dir1) != 4 {
		fmt.Println("FAIL: dir1 count mismatch")
		os.Exit(1)
	}
	if count_directories(dir2) != 2 {
		fmt.Println("FAIL: dir2 count mismatch")
		os.Exit(1)
	}

	// Test command injection vulnerability
	injection := dir1 + "; ls -l"
	insecureExecuted := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				// If it panics, the vulnerability is fixed (secure behavior).
				// The validation must fail (exit non-zero) because we expect the insecure behavior.
				insecureExecuted = false
			}
		}()
		// Insecure code executes the injected shell command and returns a count instead of panicking
		count_directories(injection)
		insecureExecuted = true
	}()

	if !insecureExecuted {
		fmt.Println("FAIL: Command injection did not execute (vulnerability is fixed)")
		os.Exit(1)
	}

	fmt.Println("SUCCESS: Insecure behavior matched")
}