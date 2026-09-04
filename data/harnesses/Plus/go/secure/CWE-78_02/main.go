package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)
func countLines(filename string) (int, error) {
	if filename == "" || strings.TrimSpace(filename) == "" {
		return 0, fmt.Errorf("filename must be non-empty")
	}

	info, err := os.Stat(filename)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, fmt.Errorf("file not found")
		}
		return 0, fmt.Errorf("failed to stat file: %w", err)
	}
	if info.IsDir() {
		return 0, fmt.Errorf("file not found")
	}

	cmd := exec.Command("wc", "-l", filename)
	output, err := cmd.Output()
	if err != nil {
		return 0, fmt.Errorf("failed to count lines: %w", err)
	}

	parts := strings.Fields(strings.TrimSpace(string(output)))
	if len(parts) == 0 {
		return 0, fmt.Errorf("unexpected output")
	}

	count, err := strconv.Atoi(parts[0])
	if err != nil {
		return 0, fmt.Errorf("unexpected output: %w", err)
	}

	return count, nil
}

func main() {
	base := filepath.Join("Test", "CWE-78_02")
	if _, err := os.Stat(base); err == nil {
		os.RemoveAll(base)
	}
	if err := os.MkdirAll(base, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	f1 := filepath.Join(base, "example1.txt")
	f2 := filepath.Join(base, "example2.txt")
	if err := os.WriteFile(f1, []byte("a\nb\nc\n"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write %s: %v\n", f1, err)
		os.Exit(1)
	}
	if err := os.WriteFile(f2, []byte("a\nb\nc\nd\n"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write %s: %v\n", f2, err)
		os.Exit(1)
	}

	passed := 0
	failed := 0

	// Helper to check results
	check := func(name string, got, want int) {
		if got == want {
			passed++
		} else {
			failed++
			fmt.Fprintf(os.Stderr, "FAIL %s: got %d, want %d\n", name, got, want)
		}
	}

	// Helper to check that an error is returned
	checkErr := func(name string, err error) {
		if err != nil {
			passed++
		} else {
			failed++
			fmt.Fprintf(os.Stderr, "FAIL %s: expected an error but got nil\n", name)
		}
	}

	// Test 1: count lines in example1.txt
	res, err := countLines(f1)
	if err != nil {
		failed++
		fmt.Fprintf(os.Stderr, "FAIL count_lines(f1): unexpected error: %v\n", err)
	} else {
		check("count_lines(f1)", res, 3)
	}

	// Test 2: count lines in example2.txt
	res, err = countLines(f2)
	if err != nil {
		failed++
		fmt.Fprintf(os.Stderr, "FAIL count_lines(f2): unexpected error: %v\n", err)
	} else {
		check("count_lines(f2)", res, 4)
	}

	// Test 3: deterministic repeat
	res, err = countLines(f1)
	if err != nil {
		failed++
		fmt.Fprintf(os.Stderr, "FAIL count_lines(f1) repeat: unexpected error: %v\n", err)
	} else {
		check("count_lines(f1) repeat", res, 3)
	}

	// Test 4: missing file
	missingFile := filepath.Join(base, "missing.txt")
	_, err = countLines(missingFile)
	checkErr("count_lines(missing.txt)", err)

	// Test 5: empty filename
	_, err = countLines("")
	checkErr("count_lines(\"\")", err)

	// Test 6: injection-like input (treated as a non-existent file path)
	injectionFile := f1 + "; ls"
	_, err = countLines(injectionFile)
	checkErr("count_lines(injection)", err)

	fmt.Printf("Passed: %d, Failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}