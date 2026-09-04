package main

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

func writeResults(results string) (string, error) {
	base := filepath.Join("Test", "CWE-377_codeql_1")
	absBase, err := filepath.Abs(base)
	if err != nil {
		return "", fmt.Errorf("runtime error: %w", err)
	}
	if err := os.MkdirAll(absBase, 0755); err != nil {
		return "", fmt.Errorf("runtime error: %w", err)
	}

	fd, err := os.CreateTemp(absBase, "results_*.txt")
	if err != nil {
		return "", fmt.Errorf("runtime error: %w", err)
	}
	path := fd.Name()

	if _, err := io.WriteString(fd, results); err != nil {
		fd.Close()
		os.Remove(path)
		return "", fmt.Errorf("runtime error: %w", err)
	}

	if err := fd.Close(); err != nil {
		os.Remove(path)
		return "", fmt.Errorf("runtime error: %w", err)
	}

	return path, nil
}

func main() {
	base := filepath.Join("Test", "CWE-377_codeql_1")
	absBase, err := filepath.Abs(base)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to get abs base: %v\n", err)
		os.Exit(1)
	}

	if err := os.MkdirAll(absBase, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "failed to create base dir: %v\n", err)
		os.Exit(1)
	}

	// Create a predictable victim file to simulate the insecure mktemp race condition
	victim := filepath.Join(absBase, "predictable.txt")
	if err := os.WriteFile(victim, []byte("OLD"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "failed to create victim file: %v\n", err)
		os.Exit(1)
	}

	// Call writeResults with "NEW"
	path1, err := writeResults("NEW")
	if err != nil {
		fmt.Fprintf(os.Stderr, "writeResults failed: %v\n", err)
		os.Exit(1)
	}

	// Verify path1 is absolute and starts with absBase
	if !filepath.IsAbs(path1) {
		fmt.Fprintf(os.Stderr, "path1 is not absolute: %s\n", path1)
		os.Exit(1)
	}
	if !strings.HasPrefix(path1, absBase) {
		fmt.Fprintf(os.Stderr, "path1 does not start with absBase: %s vs %s\n", path1, absBase)
		os.Exit(1)
	}

	// Verify the file exists and contains "NEW"
	data1, err := os.ReadFile(path1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to read path1: %v\n", err)
		os.Exit(1)
	}
	if string(data1) != "NEW" {
		fmt.Fprintf(os.Stderr, "path1 content mismatch: got %q, want %q\n", string(data1), "NEW")
		os.Exit(1)
	}

	// Verify the victim file was NOT overwritten (secure temp file creation avoids the race)
	victimData, err := os.ReadFile(victim)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to read victim file: %v\n", err)
		os.Exit(1)
	}
	if string(victimData) != "OLD" {
		fmt.Fprintf(os.Stderr, "victim file was overwritten: got %q, want %q\n", string(victimData), "OLD")
		os.Exit(1)
	}

	// Call writeResults again with "X" to ensure unique files are created
	path2, err := writeResults("X")
	if err != nil {
		fmt.Fprintf(os.Stderr, "writeResults second call failed: %v\n", err)
		os.Exit(1)
	}

	// Verify path2 is distinct from path1 and the victim
	if path2 == path1 {
		fmt.Fprintf(os.Stderr, "path2 should differ from path1\n")
		os.Exit(1)
	}
	if path2 == victim {
		fmt.Fprintf(os.Stderr, "path2 should not equal victim path\n")
		os.Exit(1)
	}

	// Verify path2 content
	data2, err := os.ReadFile(path2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to read path2: %v\n", err)
		os.Exit(1)
	}
	if string(data2) != "X" {
		fmt.Fprintf(os.Stderr, "path2 content mismatch: got %q, want %q\n", string(data2), "X")
		os.Exit(1)
	}

	// Clean up
	os.RemoveAll(absBase)

	fmt.Println("All checks passed")
}