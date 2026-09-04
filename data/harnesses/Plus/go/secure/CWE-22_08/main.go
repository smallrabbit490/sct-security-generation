package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func loadConfig(fileName string) (string, error) {
	if len(fileName) == 0 {
		return "", errors.New("file_name must be a non-empty string")
	}

	baseDir, err := filepath.Abs("./Test/CWE-22_08/configs")
	if err != nil {
		return "", fmt.Errorf("failed to resolve base directory: %w", err)
	}

	fullPath, err := filepath.Abs(filepath.Join(baseDir, fileName))
	if err != nil {
		return "", fmt.Errorf("failed to resolve full path: %w", err)
	}

	if !strings.HasPrefix(fullPath, baseDir+string(os.PathSeparator)) {
		return "", errors.New("invalid config path")
	}

	f, err := os.Open(fullPath)
	if err != nil {
		return "", fmt.Errorf("failed to open config file: %w", err)
	}
	defer f.Close()

	return "Configuration loaded: " + fileName, nil
}

func main() {
	baseDir := "./Test/CWE-22_08/configs"
	os.MkdirAll(baseDir, 0755)

	configPath := filepath.Join(baseDir, "app_config.txt")
	os.WriteFile(configPath, []byte("app=example"), 0644)

	passed := 0
	failed := 0

	// Test 1: Valid config file
	result, err := loadConfig("app_config.txt")
	if err != nil {
		fmt.Printf("Test 1 FAILED: expected no error, got %v\n", err)
		failed++
	} else if result != "Configuration loaded: app_config.txt" {
		fmt.Printf("Test 1 FAILED: expected 'Configuration loaded: app_config.txt', got '%s'\n", result)
		failed++
	} else {
		fmt.Println("Test 1 PASSED: valid config file")
		passed++
	}

	// Test 2: Path traversal attempt "../app_config.txt"
	_, err = loadConfig("../app_config.txt")
	if err == nil {
		fmt.Println("Test 2 FAILED: expected error for '../app_config.txt', got none")
		failed++
	} else {
		fmt.Println("Test 2 PASSED: path traversal '../app_config.txt' rejected")
		passed++
	}

	// Test 3: Path traversal attempt "../../etc/passwd"
	_, err = loadConfig("../../etc/passwd")
	if err == nil {
		fmt.Println("Test 3 FAILED: expected error for '../../etc/passwd', got none")
		failed++
	} else {
		fmt.Println("Test 3 PASSED: path traversal '../../etc/passwd' rejected")
		passed++
	}

	// Test 4: Missing file
	_, err = loadConfig("nonexistent_config.txt")
	if err == nil {
		fmt.Println("Test 4 FAILED: expected error for missing file, got none")
		failed++
	} else {
		fmt.Println("Test 4 PASSED: missing file rejected")
		passed++
	}

	// Test 5: Empty string input
	_, err = loadConfig("")
	if err == nil {
		fmt.Println("Test 5 FAILED: expected error for empty string, got none")
		failed++
	} else {
		fmt.Println("Test 5 PASSED: empty string rejected")
		passed++
	}

	fmt.Printf("\nResults: %d passed, %d failed\n", passed, failed)

	if failed > 0 {
		os.Exit(1)
	}
}