package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)
var validUserID = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)

func exportUserReport(userID string, reportText string) (string, error) {
	uid := strings.TrimSpace(userID)
	if uid == "" {
		return "", errors.New("empty user_id")
	}

	if !validUserID.MatchString(uid) {
		return "", errors.New("invalid user_id")
	}

	baseDir := "Test/CWE-276_09/reports"
	userDir := filepath.Join(baseDir, uid)

	err := os.MkdirAll(userDir, 0700)
	if err != nil {
		return "", err
	}

	os.Chmod(userDir, 0700)

	path := filepath.Join(userDir, "report.txt")

	err = os.WriteFile(path, []byte(reportText), 0600)
	if err != nil {
		return "", err
	}

	os.Chmod(path, 0600)

	return "Report exported.", nil
}

func assertRaises(fn func() (string, error)) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("Panic during assertRaises: %v\n", r)
			os.Exit(1)
		}
	}()
	_, err := fn()
	if err == nil {
		fmt.Println("Expected an error but none was raised")
		os.Exit(1)
	}
}

func main() {
	base := "Test/CWE-276_09/reports"

	// Clean up any previous test artifacts
	os.RemoveAll(base)

	// Valid user report
	result, err := exportUserReport("user123", "hello")
	if err != nil {
		fmt.Printf("Unexpected error: %v\n", err)
		os.Exit(1)
	}
	if result != "Report exported." {
		fmt.Printf("Unexpected result: %s\n", result)
		os.Exit(1)
	}

	userDir := filepath.Join(base, "user123")
	path := filepath.Join(userDir, "report.txt")

	info, err := os.Stat(path)
	if err != nil {
		fmt.Printf("File does not exist: %v\n", err)
		os.Exit(1)
	}
	if info.Mode().Perm() != 0600 {
		fmt.Printf("Unexpected file permissions: %o\n", info.Mode().Perm())
		os.Exit(1)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		fmt.Printf("Failed to read file: %v\n", err)
		os.Exit(1)
	}
	if string(data) != "hello" {
		fmt.Printf("Unexpected file content: %s\n", string(data))
		os.Exit(1)
	}

	dirInfo, err := os.Stat(userDir)
	if err != nil {
		fmt.Printf("Directory does not exist: %v\n", err)
		os.Exit(1)
	}
	if dirInfo.Mode().Perm() != 0700 {
		fmt.Printf("Unexpected directory permissions: %o\n", dirInfo.Mode().Perm())
		os.Exit(1)
	}

	// Another valid user_id
	result, err = exportUserReport("u_1-2", "x")
	if err != nil {
		fmt.Printf("Unexpected error: %v\n", err)
		os.Exit(1)
	}
	if result != "Report exported." {
		fmt.Printf("Unexpected result: %s\n", result)
		os.Exit(1)
	}

	userDir2 := filepath.Join(base, "u_1-2")
	dirInfo2, err := os.Stat(userDir2)
	if err != nil {
		fmt.Printf("Directory does not exist: %v\n", err)
		os.Exit(1)
	}
	if dirInfo2.Mode().Perm() != 0700 {
		fmt.Printf("Unexpected directory permissions: %o\n", dirInfo2.Mode().Perm())
		os.Exit(1)
	}

	// Invalid user_id (path separator)
	assertRaises(func() (string, error) {
		return exportUserReport("bad/user", "x")
	})

	// Invalid user_id (traversal-like)
	assertRaises(func() (string, error) {
		return exportUserReport("../evil", "x")
	})

	// Empty user_id
	assertRaises(func() (string, error) {
		return exportUserReport("   ", "x")
	})

	fmt.Println("All tests passed")
}