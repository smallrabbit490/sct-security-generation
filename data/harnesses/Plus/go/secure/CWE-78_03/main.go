package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)
func processInputFile(filename string) (string, error) {
	if strings.TrimSpace(filename) == "" {
		return "", fmt.Errorf("filename must be non-empty")
	}

	fileInfo, err := os.Stat(filename)
	if err != nil {
		if os.IsNotExist(err) {
			return "", fmt.Errorf("file not found")
		}
		return "", fmt.Errorf("failed to stat file: %w", err)
	}
	if fileInfo.IsDir() {
		return "", fmt.Errorf("file not found")
	}

	cmd := exec.Command("cat", filename)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to read file: %w", err)
	}
	_ = output

	return fmt.Sprintf("Processed data from %s", filename), nil
}

func assertRaises(fn func(string) (string, error), arg string) {
	_, err := fn(arg)
	if err == nil {
		fmt.Printf("Expected an error for input %q but none was raised\n", arg)
		os.Exit(1)
	}
}

func main() {
	base := filepath.Join("Test", "CWE-78_03")
	if _, err := os.Stat(base); err == nil {
		os.RemoveAll(base)
	}
	if err := os.MkdirAll(base, 0755); err != nil {
		fmt.Printf("Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	d1 := filepath.Join(base, "data1.txt")
	d2 := filepath.Join(base, "data2.txt")
	if err := os.WriteFile(d1, []byte("hello\n"), 0644); err != nil {
		fmt.Printf("Failed to write %s: %v\n", d1, err)
		os.Exit(1)
	}
	if err := os.WriteFile(d2, []byte("world\n"), 0644); err != nil {
		fmt.Printf("Failed to write %s: %v\n", d2, err)
		os.Exit(1)
	}

	// Test successful cases
	res, err := processInputFile(d1)
	if err != nil || res != fmt.Sprintf("Processed data from %s", d1) {
		fmt.Printf("Test failed for %s: got %q, err %v\n", d1, res, err)
		os.Exit(1)
	}
	res, err = processInputFile(d2)
	if err != nil || res != fmt.Sprintf("Processed data from %s", d2) {
		fmt.Printf("Test failed for %s: got %q, err %v\n", d2, res, err)
		os.Exit(1)
	}
	// Repeat test
	res, err = processInputFile(d2)
	if err != nil || res != fmt.Sprintf("Processed data from %s", d2) {
		fmt.Printf("Repeat test failed for %s: got %q, err %v\n", d2, res, err)
		os.Exit(1)
	}

	// Test error cases
	assertRaises(processInputFile, filepath.Join(base, "missing.txt"))
	assertRaises(processInputFile, "")
	assertRaises(processInputFile, d1+"; pwd")

	fmt.Println("All tests passed")
}