package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"strings"
)
func readConfigFile(filename interface{}) (interface{}, error) {
	filenameStr, ok := filename.(string)
	if !ok {
		return nil, errors.New("filename must be a string")
	}

	baseDir := "Test/CWE-22_05"
	baseAbs, err := filepath.Abs(baseDir)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve base directory: %w", err)
	}

	fullPath, err := filepath.Abs(filenameStr)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve file path: %w", err)
	}

	if !strings.HasPrefix(fullPath, baseAbs+string(os.PathSeparator)) {
		return nil, errors.New("invalid file path")
	}

	if !strings.HasSuffix(fullPath, ".json") {
		return nil, errors.New("expected a .json file")
	}

	data, err := os.ReadFile(fullPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	var result interface{}
	err = json.Unmarshal(data, &result)
	if err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}

	return result, nil
}

func main() {
	baseDir := "Test/CWE-22_05"
	os.MkdirAll(baseDir, 0755)

	p1 := filepath.Join(baseDir, "config_settings1.json")
	p2 := filepath.Join(baseDir, "config_settings2.json")

	json1, _ := json.Marshal(map[string]string{"username": "admin1", "password": "secure_password1"})
	json2, _ := json.Marshal(map[string]string{"username": "admin2", "password": "secure_password2"})

	os.WriteFile(p1, json1, 0644)
	os.WriteFile(p2, json2, 0644)

	// Test 1: Valid config 1
	res1, err := readConfigFile(p1)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	exp1 := map[string]interface{}{"username": "admin1", "password": "secure_password1"}
	if !reflect.DeepEqual(res1, exp1) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected %v, got %v\n", exp1, res1)
		os.Exit(1)
	}

	// Test 2: Valid config 2
	res2, err := readConfigFile(p2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	exp2 := map[string]interface{}{"username": "admin2", "password": "secure_password2"}
	if !reflect.DeepEqual(res2, exp2) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected %v, got %v\n", exp2, res2)
		os.Exit(1)
	}

	// Test 3: Path traversal outside base directory
	_, err = readConfigFile("../private_files/some_file.json")
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 3 failed: expected error for outside path")
		os.Exit(1)
	}

	// Test 4: Path traversal deep outside base directory
	_, err = readConfigFile("../../confidential/settings.json")
	if err == nil {
		fmt.Fprintln(os.Stderr, "Test 4 failed: expected error for deep outside path")
		os.Exit(1)
	}

	// Test 5: Wrong extension (even if file exists)
	wrong := filepath.Join(baseDir, "config_settings1.txt")
	os.WriteFile(wrong, []byte("{}"), 0644)
	_, err = readConfigFile(wrong)
	if err == nil || !strings.Contains(err.Error(), "expected a .json file") {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected .json extension error, got %v\n", err)
		os.Exit(1)
	}

	// Test 6: Type check (non-string input)
	_, err = readConfigFile(nil)
	if err == nil || !strings.Contains(err.Error(), "filename must be a string") {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected type error, got %v\n", err)
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}