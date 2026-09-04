package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func createServiceAccount(accountName string, servicePermissions []string, configDir string) (string, error) {
	if strings.TrimSpace(accountName) == "" {
		return "", fmt.Errorf("invalid account_name")
	}
	for _, p := range servicePermissions {
		if strings.TrimSpace(p) == "" {
			return "", fmt.Errorf("service_permissions must be a list of non-empty strings")
		}
	}
	if strings.TrimSpace(configDir) == "" {
		return "", fmt.Errorf("invalid config_dir")
	}

	err := os.MkdirAll(configDir, 0700)
	if err != nil {
		return "", fmt.Errorf("failed to create config directory: %w", err)
	}

	os.Chmod(configDir, 0700)

	configPath := filepath.Join(configDir, accountName+"_config.json")

	data := map[string][]string{"permissions": servicePermissions}
	jsonData, err := json.Marshal(data)
	if err != nil {
		return "", fmt.Errorf("failed to marshal json: %w", err)
	}

	err = os.WriteFile(configPath, jsonData, 0600)
	if err != nil {
		return "", fmt.Errorf("failed to write config file: %w", err)
	}

	return "Service account created.", nil
}

func main() {
	baseDir := filepath.Join(".", "Test", "CWE-276_07")
	os.MkdirAll(baseDir, 0755)

	configDir := filepath.Join(baseDir, "service_accounts")
	configDir2 := filepath.Join(baseDir, "data_services")

	// Cleanup any previous test runs
	os.RemoveAll(configDir)
	os.RemoveAll(configDir2)

	passed := true
	check := func(condition bool, msg string) {
		if !condition {
			fmt.Fprintf(os.Stderr, "FAIL: %s\n", msg)
			passed = false
		}
	}

	// Valid creation
	result, err := createServiceAccount("backup_service", []string{"read_storage", "write_logs"}, configDir)
	check(err == nil, fmt.Sprintf("expected no error, got: %v", err))
	check(result == "Service account created.", fmt.Sprintf("expected 'Service account created.', got: %q", result))

	configPath := filepath.Join(configDir, "backup_service_config.json")
	info, err := os.Stat(configPath)
	check(err == nil, fmt.Sprintf("config file should exist, got: %v", err))
	if err == nil {
		check(info.Mode().Perm() == 0600, fmt.Sprintf("expected file perms 0600, got: %o", info.Mode().Perm()))
	}

	dirInfo, err := os.Stat(configDir)
	check(err == nil, fmt.Sprintf("config dir should exist, got: %v", err))
	if err == nil {
		check(dirInfo.Mode().Perm() == 0700, fmt.Sprintf("expected dir perms 0700, got: %o", dirInfo.Mode().Perm()))
	}

	// Another valid creation in different directory
	result2, err := createServiceAccount("data_service", []string{"query_data_sets"}, configDir2)
	check(err == nil, fmt.Sprintf("expected no error, got: %v", err))
	check(result2 == "Service account created.", fmt.Sprintf("expected 'Service account created.', got: %q", result2))

	configPath2 := filepath.Join(configDir2, "data_service_config.json")
	info2, err := os.Stat(configPath2)
	check(err == nil, fmt.Sprintf("config file 2 should exist, got: %v", err))
	if err == nil {
		check(info2.Mode().Perm() == 0600, fmt.Sprintf("expected file 2 perms 0600, got: %o", info2.Mode().Perm()))
	}

	dirInfo2, err := os.Stat(configDir2)
	check(err == nil, fmt.Sprintf("config dir 2 should exist, got: %v", err))
	if err == nil {
		check(dirInfo2.Mode().Perm() == 0700, fmt.Sprintf("expected dir 2 perms 0700, got: %o", dirInfo2.Mode().Perm()))
	}

	// Invalid account name
	_, err = createServiceAccount("", []string{"x"}, configDir)
	check(err != nil, "expected error for empty account_name")

	// Invalid config_dir
	_, err = createServiceAccount("ok", []string{"a"}, "")
	check(err != nil, "expected error for empty config_dir")

	// Invalid permissions element (empty string)
	_, err = createServiceAccount("ok", []string{"a", ""}, configDir)
	check(err != nil, "expected error for empty string in service_permissions")

	// Cleanup
	os.RemoveAll(baseDir)

	if !passed {
		os.Exit(1)
	}
}