package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)
func appendAuditLog(logDate, eventText string) (int, error) {
	if logDate == "" {
		return 0, fmt.Errorf("log_date must be non-empty")
	}

	dateRegex := regexp.MustCompile(`^\d{4}-\d{2}-\d{2}$`)
	if !dateRegex.MatchString(logDate) {
		return 0, fmt.Errorf("invalid log_date format")
	}

	baseDir, err := filepath.Abs(filepath.Clean("./Test/CWE-22_10/logs"))
	if err != nil {
		return 0, fmt.Errorf("failed to resolve base directory: %w", err)
	}

	if err := os.MkdirAll(baseDir, 0755); err != nil {
		return 0, fmt.Errorf("failed to create base directory: %w", err)
	}

	filename := logDate + ".log"
	if filepath.Base(filename) != filename {
		return 0, fmt.Errorf("invalid log file name")
	}

	path := filepath.Join(baseDir, filename)
	cleanPath, err := filepath.Abs(filepath.Clean(path))
	if err != nil {
		return 0, fmt.Errorf("failed to resolve log file path: %w", err)
	}

	if cleanPath != baseDir && !strings.HasPrefix(cleanPath, baseDir+string(os.PathSeparator)) {
		return 0, fmt.Errorf("unauthorized access attempt detected")
	}

	file, err := os.OpenFile(cleanPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return 0, fmt.Errorf("failed to open log file: %w", err)
	}
	if _, err := file.WriteString(eventText + "\n"); err != nil {
		file.Close()
		return 0, fmt.Errorf("failed to write to log file: %w", err)
	}
	file.Close()

	readFile, err := os.Open(cleanPath)
	if err != nil {
		return 0, fmt.Errorf("failed to open log file for reading: %w", err)
	}
	defer readFile.Close()

	lineCount := 0
	scanner := bufio.NewScanner(readFile)
	for scanner.Scan() {
		lineCount++
	}
	if err := scanner.Err(); err != nil {
		return 0, fmt.Errorf("failed to read log file: %w", err)
	}

	return lineCount, nil
}

func main() {
	root := "./Test/CWE-22_10"
	os.RemoveAll(root)
	os.MkdirAll(root, 0755)

	// normal appends
	n1, err := appendAuditLog("2026-01-21", "login userA")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if n1 != 1 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 1, got %d\n", n1)
		os.Exit(1)
	}

	n2, err := appendAuditLog("2026-01-21", "logout userA")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	if n2 != 2 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 2, got %d\n", n2)
		os.Exit(1)
	}

	n3, err := appendAuditLog("2026-01-22", "login userB")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: %v\n", err)
		os.Exit(1)
	}
	if n3 != 1 {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected 1, got %d\n", n3)
		os.Exit(1)
	}

	// verify file content exists where expected
	p := filepath.Join("./Test/CWE-22_10/logs", "2026-01-21.log")
	content, err := os.ReadFile(p)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read log file: %v\n", err)
		os.Exit(1)
	}
	lines := strings.Split(strings.TrimRight(string(content), "\n"), "\n")
	if len(lines) != 2 || lines[0] != "login userA" || lines[1] != "logout userA" {
		fmt.Fprintf(os.Stderr, "Test 4 failed: unexpected content %v\n", lines)
		os.Exit(1)
	}

	// traversal / invalid date formats must raise error
	badInputs := []string{"../../etc/passwd", "2026-1-21", "2026-01-21/../../pwn", "2026-01-21.."}
	for _, badDate := range badInputs {
		_, err := appendAuditLog(badDate, "x")
		if err == nil {
			fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for input %q, got none\n", badDate)
			os.Exit(1)
		}
	}

	// empty string must raise error
	_, err = appendAuditLog("", "x")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected error for empty log_date, got none\n")
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}