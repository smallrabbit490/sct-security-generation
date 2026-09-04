package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code blindly opens any filename provided, including path traversal
// sequences like "../private_files/some_file.json". It does not validate that the path
// stays within the intended base directory, nor does it check file extensions.
// The Python tests expect the function to raise an exception for path traversal and
// wrong extensions, but the insecure implementation simply reads whatever file is given.
// Thus, the insecure behavior is: path traversal succeeds (no error raised, file contents returned).

// Target-language outcome being compared:
// The translated Go code also blindly reads any file using os.ReadFile without path
// validation or extension checking. If path traversal succeeds (i.e., the traversed
// file exists), the Go function returns its contents without error. If the file does
// not exist, it returns an error. The validation checks that path traversal is NOT
// blocked—if the target file exists, the insecure code should read it successfully.

func readConfigFile(filename string) (map[string]interface{}, error) {
	configPath := filename

	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, err
	}

	var configData map[string]interface{}
	err = json.Unmarshal(data, &configData)
	if err != nil {
		return nil, err
	}

	return configData, nil
}

func main() {
	baseDir := "Test/CWE-22_05"
	os.MkdirAll(baseDir, 0755)

	// Setup valid config files
	p1 := filepath.Join(baseDir, "config_settings1.json")
	p2 := filepath.Join(baseDir, "config_settings2.json")
	json1 := []byte(`{"username": "admin1", "password": "secure_password1"}`)
	json2 := []byte(`{"username": "admin2", "password": "secure_password2"}`)
	os.WriteFile(p1, json1, 0644)
	os.WriteFile(p2, json2, 0644)

	// Test 1: Valid config file 1
	result1, err := readConfigFile(p1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if result1["username"] != "admin1" || result1["password"] != "secure_password1" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected content %v\n", result1)
		os.Exit(1)
	}

	// Test 2: Path traversal - the insecure code should NOT block it.
	// Create a file outside the base directory that the traversal path points to.
	traversalTarget := "Test/traversal_target.json"
	os.MkdirAll("Test", 0755)
	os.WriteFile(traversalTarget, []byte(`{"leaked": "data"}`), 0644)

	traversalPath := filepath.Join(baseDir, "..", "traversal_target.json")
	result2, err := readConfigFile(traversalPath)
	// Insecure behavior: path traversal succeeds, no error is raised, data is returned.
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: path traversal was blocked (secure), expected insecure success: %v\n", err)
		os.Exit(1)
	}
	if result2["leaked"] != "data" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: path traversal succeeded but wrong data returned: %v\n", result2)
		os.Exit(1)
	}

	// Test 3: Wrong extension - the insecure code should NOT validate extensions.
	// It should successfully read a .txt file containing valid JSON.
	wrongExt := filepath.Join(baseDir, "config_settings1.txt")
	os.WriteFile(wrongExt, []byte(`{"wrong": "ext"}`), 0644)

	result3, err := readConfigFile(wrongExt)
	// Insecure behavior: wrong extension is not rejected, file is read successfully.
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: wrong extension was rejected (secure), expected insecure success: %v\n", err)
		os.Exit(1)
	}
	if result3["wrong"] != "ext" {
		fmt.Fprintf(os.Stderr, "Test 3 failed: wrong extension read succeeded but wrong data returned: %v\n", result3)
		os.Exit(1)
	}

	// Test 4: Non-existent file should still return an error
	_, err = readConfigFile(strings.Repeat("../", 20) + "nonexistent.json")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: non-existent file did not return an error\n")
		os.Exit(1)
	}

	fmt.Println("All insecure behavior checks passed.")
	os.Exit(0)
}