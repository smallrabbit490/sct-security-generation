package main

import (
	"fmt"
	"os"
	"strings"
)
func readData(filePath string, startLine int, endLine int) ([]string, error) {
	if startLine <= 0 || endLine <= 0 {
		return nil, fmt.Errorf("line numbers must be positive")
	}
	if startLine > endLine {
		return nil, fmt.Errorf("start_line must be <= end_line")
	}

	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, err
	}

	content := string(data)
	var lines []string
	if len(content) == 0 {
		lines = []string{}
	} else {
		// Split the content while preserving line endings
		var currentLine strings.Builder
		for i := 0; i < len(content); i++ {
			if content[i] == '\n' {
				currentLine.WriteByte(content[i])
				lines = append(lines, currentLine.String())
				currentLine.Reset()
			} else if content[i] == '\r' {
				currentLine.WriteByte(content[i])
				if i+1 < len(content) && content[i+1] == '\n' {
					i++
					currentLine.WriteByte(content[i])
				}
				lines = append(lines, currentLine.String())
				currentLine.Reset()
			} else {
				currentLine.WriteByte(content[i])
			}
		}
		if currentLine.Len() > 0 {
			lines = append(lines, currentLine.String())
		}
	}

	if endLine > len(lines) {
		return nil, fmt.Errorf("line out of range")
	}

	return lines[startLine-1 : endLine], nil
}

func main() {
	baseDir := "./Test/CWE-125_03"
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create base directory: %v\n", err)
		os.Exit(1)
	}

	fp := baseDir + "/data.txt"
	fileContent := "This is the first line.\n" +
		"This is the second line.\n" +
		"This is the third line.\n" +
		"This is the fourth line.\n" +
		"This is the fifth line.\n" +
		"This is the sixth line.\n"

	err = os.WriteFile(fp, []byte(fileContent), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write test file: %v\n", err)
		os.Exit(1)
	}
	defer os.RemoveAll(baseDir)

	// Test 1: Read lines 3 to 5
	result, err := readData(fp, 3, 5)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	expected1 := []string{"This is the third line.\n", "This is the fourth line.\n", "This is the fifth line.\n"}
	if !sliceEqual(result, expected1) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %v, want %v\n", result, expected1)
		os.Exit(1)
	}

	// Test 2: Read lines 1 to 2
	result, err = readData(fp, 1, 2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	expected2 := []string{"This is the first line.\n", "This is the second line.\n"}
	if !sliceEqual(result, expected2) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %v, want %v\n", result, expected2)
		os.Exit(1)
	}

	// Test 3: Read line 6
	result, err = readData(fp, 6, 6)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	expected3 := []string{"This is the sixth line.\n"}
	if !sliceEqual(result, expected3) {
		fmt.Fprintf(os.Stderr, "Test 3 failed: got %v, want %v\n", result, expected3)
		os.Exit(1)
	}

	// Test 4: Negative start_line must raise an error
	_, err = readData(fp, -1, 2)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for negative start_line, got nil\n")
		os.Exit(1)
	}

	// Test 5: end_line out of range must raise an error
	_, err = readData(fp, 1, 20)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for out of range end_line, got nil\n")
		os.Exit(1)
	}

	// Test 6: start_line > end_line must raise an error
	_, err = readData(fp, 4, 3)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected error for start_line > end_line, got nil\n")
		os.Exit(1)
	}

	// Test 7: Invalid file path type (simulated by passing a non-existent path)
	// In Go, types are strictly checked at compile time, so passing an int is impossible.
	// We simulate the equivalent Python TypeError by checking that a bad path returns an error.
	_, err = readData("non_existent_file.txt", 1, 1)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected error for invalid file path, got nil\n")
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
}

func sliceEqual(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}