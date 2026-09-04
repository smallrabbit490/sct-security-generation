package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func accessSensitiveFile(userRole, fileName, baseDirectory string) (string, error) {
	if userRole == "" || fileName == "" || baseDirectory == "" {
		return "", errors.New("inputs must be non-empty strings")
	}

	// prevent path traversal by requiring a simple file name
	if filepath.Base(fileName) != fileName {
		return "", errors.New("file_name must not contain path separators")
	}

	baseAbs, err := filepath.Abs(baseDirectory)
	if err != nil {
		return "", fmt.Errorf("failed to resolve base directory: %w", err)
	}
	fullPath, err := filepath.Abs(filepath.Join(baseAbs, fileName))
	if err != nil {
		return "", fmt.Errorf("failed to resolve full path: %w", err)
	}

	// prevent path traversal
	if !strings.HasPrefix(fullPath, baseAbs+string(os.PathSeparator)) && fullPath != baseAbs {
		return "", errors.New("invalid path")
	}

	fileInfo, err := os.Stat(fullPath)
	if err != nil {
		if os.IsNotExist(err) {
			return "File not found.", nil
		}
		return "", fmt.Errorf("failed to check file existence: %w", err)
	}
	if fileInfo.IsDir() {
		return "File not found.", nil
	}

	allowedRoles := map[string][]string{
		"confidential_report.txt": {"admin", "manager"},
		"public_report.txt":       {"admin", "manager", "employee", "guest"},
	}

	if roles, exists := allowedRoles[fileName]; exists {
		for _, role := range roles {
			if role == userRole {
				return "Opened.", nil
			}
		}
	}

	return "Not allowed.", nil
}

func assertEqual(got, want string) {
	if got != want {
		fmt.Printf("FAIL: got %q, want %q\n", got, want)
		os.Exit(1)
	}
}

func assertError(err error, substr string) {
	if err == nil {
		fmt.Printf("FAIL: expected error containing %q but got nil\n", substr)
		os.Exit(1)
	}
	if !strings.Contains(err.Error(), substr) {
		fmt.Printf("FAIL: expected error containing %q but got %q\n", substr, err.Error())
		os.Exit(1)
	}
}

func main() {
	baseDirectory := filepath.Join(".", "Test", "CWE-862_CWE-287_CWE-306_CWE-863_06")

	if err := os.MkdirAll(baseDirectory, 0755); err != nil {
		fmt.Printf("FAIL: could not create base directory: %v\n", err)
		os.Exit(1)
	}

	confidentialFilePath := filepath.Join(baseDirectory, "confidential_report.txt")
	publicFilePath := filepath.Join(baseDirectory, "public_report.txt")

	if err := os.WriteFile(confidentialFilePath, []byte("Confidential content here."), 0644); err != nil {
		fmt.Printf("FAIL: could not write confidential file: %v\n", err)
		os.Exit(1)
	}
	if err := os.WriteFile(publicFilePath, []byte("Public content here."), 0644); err != nil {
		fmt.Printf("FAIL: could not write public file: %v\n", err)
		os.Exit(1)
	}

	// opened
	result, err := accessSensitiveFile("admin", "confidential_report.txt", baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(result, "Opened.")

	result, err = accessSensitiveFile("guest", "public_report.txt", baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(result, "Opened.")

	result, err = accessSensitiveFile("employee", "public_report.txt", baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(result, "Opened.")

	// not allowed
	result, err = accessSensitiveFile("guest", "confidential_report.txt", baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(result, "Not allowed.")

	result, err = accessSensitiveFile("employee", "confidential_report.txt", baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(result, "Not allowed.")

	// file not found
	result, err = accessSensitiveFile("guest", "non_existing_file.txt", baseDirectory)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		os.Exit(1)
	}
	assertEqual(result, "File not found.")

	// invalid inputs must raise error
	_, err = accessSensitiveFile("admin", "../confidential_report.txt", baseDirectory)
	assertError(err, "file_name must not contain path separators")

	_, err = accessSensitiveFile("", "public_report.txt", baseDirectory)
	assertError(err, "inputs must be non-empty strings")

	fmt.Println("All tests passed.")
}