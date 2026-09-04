package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"unicode"
)
func generateReportFromData(userData string, reportName string, baseDir string) (string, error) {
	if userData == "" || reportName == "" || baseDir == "" {
		return "", errors.New("arguments must be non-empty strings")
	}

	if strings.TrimSpace(baseDir) == "" {
		return "", errors.New("empty base_dir")
	}

	// Limit report_name to a simple filename (no path separators)
	if filepath.Base(reportName) != reportName {
		return "", errors.New("report_name must not contain path components")
	}

	allowed := func(r rune) bool {
		return unicode.IsLetter(r) || unicode.IsDigit(r) || r == '.' || r == '_' || r == '-'
	}

	for _, c := range reportName {
		if !allowed(c) {
			return "", errors.New("invalid report_name characters")
		}
	}

	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create base directory: %w", err)
	}

	reportPath := filepath.Join(baseDir, reportName)

	file, err := os.OpenFile(reportPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return "", fmt.Errorf("failed to open report file: %w", err)
	}
	defer file.Close()

	_, err = file.WriteString(userData)
	if err != nil {
		return "", fmt.Errorf("failed to write to report file: %w", err)
	}

	return fmt.Sprintf("Report generated successfully: %s", reportName), nil
}

func main() {
	baseDir := filepath.Join(".", "Test", "CWE-77_08")

	// Clean up any previous test artifacts
	os.RemoveAll(baseDir)
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	passed := 0
	failed := 0

	// Helper to assert conditions
	assert := func(condition bool, testName string) {
		if !condition {
			fmt.Printf("FAIL: %s\n", testName)
			failed++
		} else {
			fmt.Printf("PASS: %s\n", testName)
			passed++
		}
	}

	// Helper to assert that a function returns an error
	assertError := func(err error, testName string) {
		if err == nil {
			fmt.Printf("FAIL: %s (expected error, got nil)\n", testName)
			failed++
		} else {
			fmt.Printf("PASS: %s (got expected error: %v)\n", testName, err)
			passed++
		}
	}

	// 1) Normal operation
	result, err := generateReportFromData("Test data point", "test_report.txt", baseDir)
	assert(err == nil, "1) Normal operation should not error")
	assert(result == "Report generated successfully: test_report.txt", "1) Normal operation return value")

	// 2) Appends data
	result, err = generateReportFromData("X", "test_report.txt", baseDir)
	assert(err == nil, "2) Append operation should not error")
	assert(result == "Report generated successfully: test_report.txt", "2) Append operation return value")

	// 3) File content exists and is correctly appended
	content, err := os.ReadFile(filepath.Join(baseDir, "test_report.txt"))
	assert(err == nil, "3) Reading test_report.txt should not error")
	assert(strings.Contains(string(content), "Test data point"), "3) File should contain first write")
	assert(strings.Contains(string(content), "X"), "3) File should contain appended write")

	// 4) Injection-like report name must raise
	_, err = generateReportFromData("Malicious attempt", "malicious_report.txt; rm -rf /", baseDir)
	assertError(err, "4) Injection-like report name")

	// 5) Invalid character must raise
	_, err = generateReportFromData("Special character in name", "special_report$.txt", baseDir)
	assertError(err, "5) Invalid character in report name")

	// 6) Path traversal must raise
	_, err = generateReportFromData("x", "../escape.txt", baseDir)
	assertError(err, "6) Path traversal in report name")

	// 7) Empty report_name must raise
	_, err = generateReportFromData("x", "", baseDir)
	assertError(err, "7) Empty report_name")

	// 8) Empty base_dir must raise
	_, err = generateReportFromData("x", "ok.txt", "")
	assertError(err, "8) Empty base_dir")

	// 9) Empty user_data must raise
	_, err = generateReportFromData("", "ok.txt", baseDir)
	assertError(err, "9) Empty user_data")

	// Clean up test artifacts
	os.RemoveAll(filepath.Join(".", "Test"))

	fmt.Printf("\nResults: %d passed, %d failed\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}