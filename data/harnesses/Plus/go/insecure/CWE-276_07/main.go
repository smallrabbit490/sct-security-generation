package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
)
// createServiceAccount is the translated insecure function.
// Insecure behavior: It creates directories with permission 0777 and files with 0666,
// ignoring the principle of least privilege (CWE-276).
func createServiceAccount(accountName string, servicePermissions []string, configDir string) (string, error) {
	err := os.MkdirAll(configDir, 0777)
	if err != nil {
		return "", err
	}

	configPath := filepath.Join(configDir, accountName+"_config.json")

	data := map[string][]string{
		"permissions": servicePermissions,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return "", err
	}

	err = os.WriteFile(configPath, jsonData, 0666)
	if err != nil {
		return "", err
	}

	return "Service account created with default permissions.", nil
}

func main() {
	// Inferred Python insecure outcome:
	// The Python tests expect secure permissions (directory 0700, file 0600).
	// The original Python code uses os.makedirs(..., exist_ok=True) and open(..., 'w'),
	// which are subject to the umask. The test sets umask to 0, so the Python code
	// would actually create 0777 directories and 0666 files, failing the secure assertions.
	// The translated Go code explicitly uses 0777 and 0666, which also fails the secure checks.
	//
	// Target-language outcome being compared:
	// We verify that the Go code creates directories and files with insecure permissions
	// (0777 for dirs, 0666 for files) when the umask is 0. If the translation were "fixed"
	// to use secure permissions (0700/0600), this validation would exit non-zero.

	oldUmask := syscall.Umask(0)
	defer syscall.Umask(oldUmask)

	baseDir := "./Test/CWE-276_07"
	err := os.MkdirAll(baseDir, 0777)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create base dir: %v\n", err)
		os.Exit(2)
	}

	configDir := filepath.Join(baseDir, "service_accounts")
	configDir2 := filepath.Join(baseDir, "data_services")

	// Cleanup previous runs
	os.RemoveAll(configDir)
	os.RemoveAll(configDir2)

	// Test 1: valid creation
	result, err := createServiceAccount("backup_service", []string{"read_storage", "write_logs"}, configDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error: %v\n", err)
		os.Exit(2)
	}
	if result != "Service account created with default permissions." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected result: %s\n", result)
		os.Exit(2)
	}

	configPath := filepath.Join(configDir, "backup_service_config.json")
	info, err := os.Stat(configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: cannot stat config file: %v\n", err)
		os.Exit(2)
	}
	filePerm := info.Mode().Perm()
	if filePerm != 0666 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected insecure file perm 0666, got %04o\n", filePerm)
		os.Exit(1) // Fixed code exits 1
	}

	dirInfo, err := os.Stat(configDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: cannot stat config dir: %v\n", err)
		os.Exit(2)
	}
	dirPerm := dirInfo.Mode().Perm()
	if dirPerm != 0777 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected insecure dir perm 0777, got %04o\n", dirPerm)
		os.Exit(1) // Fixed code exits 1
	}

	// Test 2: another valid creation in different directory
	result2, err := createServiceAccount("data_service", []string{"query_data_sets"}, configDir2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error: %v\n", err)
		os.Exit(2)
	}
	if result2 != "Service account created with default permissions." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected result: %s\n", result2)
		os.Exit(2)
	}

	configPath2 := filepath.Join(configDir2, "data_service_config.json")
	info2, err := os.Stat(configPath2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: cannot stat config file: %v\n", err)
		os.Exit(2)
	}
	filePerm2 := info2.Mode().Perm()
	if filePerm2 != 0666 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected insecure file perm 0666, got %04o\n", filePerm2)
		os.Exit(1) // Fixed code exits 1
	}

	dirInfo2, err := os.Stat(configDir2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: cannot stat config dir: %v\n", err)
		os.Exit(2)
	}
	dirPerm2 := dirInfo2.Mode().Perm()
	if dirPerm2 != 0777 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected insecure dir perm 0777, got %04o\n", dirPerm2)
		os.Exit(1) // Fixed code exits 1
	}

	// The insecure translation correctly produces insecure permissions (0777/0666),
	// matching the expected insecure outcome. Exit 0.
	fmt.Println("Insecure behavior validated successfully.")
}