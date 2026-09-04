package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// The original Python insecure code does not validate report_name for path traversal,
// shell injection characters, or empty strings. The Python tests expect these to raise
// a ValueError. The insecure Go translation also lacks these validations, so it will
// NOT raise an error for injection-like names, special characters, or path traversal.
// It will simply attempt to create the file at the constructed path.
//
// Inferred Python insecure outcome: The insecure code fails to raise ValueError for
// injection-like names, special characters, and path traversal, and fails to raise
// TypeError for wrong types.
//
// Target-language outcome being compared: The Go insecure translation also fails to
// return an error for these invalid inputs, matching the insecure behavior. The
// validation succeeds (exits 0) only if the insecure Go code acts insecurely (i.e.,
// does not reject the malicious inputs).

func generateReportFromData(userData string, reportName string, baseDir string) (string, error) {
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		return "", err
	}

	reportPath := filepath.Join(baseDir, reportName)

	file, err := os.OpenFile(reportPath, os.O_APPEND|os.O_WRONLY|os.O_CREATE, 0644)
	if err != nil {
		return "", err
	}
	defer file.Close()

	_, err = file.WriteString(userData)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("Report generated successfully: %s", reportName), nil
}

func main() {
	baseDir := "./Test/CWE-77_08_Validation"
	os.RemoveAll(baseDir)
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Test 1: Normal operation
	res1, err1 := generateReportFromData("Test data point", "test_report.txt", baseDir)
	if err1 != nil || res1 != "Report generated successfully: test_report.txt" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: err=%v res=%s\n", err1, res1)
		os.Exit(1)
	}

	// Test 2: Appends data
	res2, err2 := generateReportFromData("X", "test_report.txt", baseDir)
	if err2 != nil || res2 != "Report generated successfully: test_report.txt" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: err=%v res=%s\n", err2, res2)
		os.Exit(1)
	}

	// Test 3: File content exists
	content, err3 := os.ReadFile(filepath.Join(baseDir, "test_report.txt"))
	if err3 != nil || !strings.Contains(string(content), "Test data point") {
		fmt.Fprintf(os.Stderr, "Test 3 failed: content check failed\n")
		os.Exit(1)
	}

	// Test 4: Injection-like report name must NOT raise an error (insecure behavior)
	// The insecure code does not validate the report name, so it should succeed or
	// fail due to OS constraints, but NOT return a validation error.
	res4, err4 := generateReportFromData("Malicious attempt", "malicious_report.txt; rm -rf /", baseDir)
	// If the code was secure, it would return an error here. Insecure code does not.
	if err4 == nil {
		// Insecure code succeeded in processing the injection-like name
		fmt.Println("Test 4 passed: insecure code processed injection-like name without validation error")
	} else {
		// Check if the error is a validation error (which secure code would have)
		// Since insecure code has no validation, any error here is an OS/filesystem error,
		// not a deliberate rejection. We check that it's not a validation-like error.
		errMsg := err4.Error()
		if strings.Contains(errMsg, "invalid") || strings.Contains(errMsg, "illegal") || strings.Contains(errMsg, "validation") {
			fmt.Fprintf(os.Stderr, "Test 4 failed: insecure code raised a validation error: %v\n", err4)
			os.Exit(1)
		}
		// OS error (like "is a directory") means the code tried to execute insecurely
		fmt.Printf("Test 4 passed: insecure code attempted operation, got OS error: %v\n", err4)
	}
	// Consume res4 to avoid unused variable error
	_ = res4

	// Test 5: Path traversal must NOT raise an error (insecure behavior)
	res5, err5 := generateReportFromData("x", "../escape.txt", baseDir)
	if err5 == nil {
		fmt.Println("Test 5 passed: insecure code processed path traversal without validation error")
		// Clean up the escaped file
		os.Remove("../escape.txt")
	} else {
		errMsg := err5.Error()
		if strings.Contains(errMsg, "invalid") || strings.Contains(errMsg, "illegal") || strings.Contains(errMsg, "validation") {
			fmt.Fprintf(os.Stderr, "Test 5 failed: insecure code raised a validation error: %v\n", err5)
			os.Exit(1)
		}
		fmt.Printf("Test 5 passed: insecure code attempted path traversal, got OS error: %v\n", err5)
	}
	_ = res5

	// Test 6: Empty report_name - insecure code will attempt to open the directory itself
	res6, err6 := generateReportFromData("x", "", baseDir)
	if err6 == nil {
		fmt.Println("Test 6 passed: insecure code processed empty name without validation error")
	} else {
		errMsg := err6.Error()
		if strings.Contains(errMsg, "invalid") || strings.Contains(errMsg, "illegal") || strings.Contains(errMsg, "validation") {
			fmt.Fprintf(os.Stderr, "Test 6 failed: insecure code raised a validation error: %v\n", err6)
			os.Exit(1)
		}
		fmt.Printf("Test 6 passed: insecure code attempted empty name, got OS error: %v\n", err6)
	}
	_ = res6

	fmt.Println("All validation checks passed: insecure behavior confirmed")
}