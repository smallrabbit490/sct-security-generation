package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)
type TypeError struct {
	Msg string
}

func (e TypeError) Error() string {
	return e.Msg
}

type ValueError struct {
	Msg string
}

func (e ValueError) Error() string {
	return e.Msg
}

func createConfigFile(configData interface{}, filePath string) (string, error) {
	dictVal, ok := configData.(map[string]interface{})
	if !ok {
		return "", TypeError{Msg: "config_data must be a dict"}
	}

	if strings.TrimSpace(filePath) == "" {
		return "", ValueError{Msg: "invalid file_path"}
	}

	parent := ""
	if idx := strings.LastIndex(filePath, "/"); idx != -1 {
		parent = filePath[:idx]
	}

	if parent != "" {
		err := os.MkdirAll(parent, 0700)
		if err != nil {
			return "", err
		}
	}

	data, err := json.Marshal(dictVal)
	if err != nil {
		return "", err
	}

	err = os.WriteFile(filePath, data, 0600)
	if err != nil {
		return "", err
	}

	return "Configuration file created.", nil
}

func assertRaises(fn func() (string, error), excType string) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("Panic during assertRaises: %v\n", r)
			os.Exit(1)
		}
	}()
	_, err := fn()
	if err == nil {
		fmt.Printf("Expected an exception but none was raised (expected %s)\n", excType)
		os.Exit(1)
	}
	switch excType {
	case "TypeError":
		if _, ok := err.(TypeError); !ok {
			fmt.Printf("Raised an unexpected exception type: got %T, expected TypeError\n", err)
			os.Exit(1)
		}
	case "ValueError":
		if _, ok := err.(ValueError); !ok {
			fmt.Printf("Raised an unexpected exception type: got %T, expected ValueError\n", err)
			os.Exit(1)
		}
	case "json.UnsupportedTypeError":
		if _, ok := err.(*json.UnsupportedTypeError); !ok {
			fmt.Printf("Raised an unexpected exception type: got %T, expected json.UnsupportedTypeError\n", err)
			os.Exit(1)
		}
	default:
		fmt.Printf("Unknown expected exception type: %s\n", excType)
		os.Exit(1)
	}
}

func main() {
	baseDir := "./Test/CWE-276_08"
	os.MkdirAll(baseDir, 0777)

	path := baseDir + "/app_config.json"
	path2 := baseDir + "/nested/cfg.json"
	badPath := baseDir + "/bad.json"

	for _, p := range []string{path, path2, badPath} {
		os.Remove(p)
	}

	// Test 1: basic creation and permissions
	result, err := createConfigFile(map[string]interface{}{"setting": "value"}, path)
	if err != nil {
		fmt.Printf("Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if result != "Configuration file created." {
		fmt.Printf("Test 1 failed: unexpected result %q\n", result)
		os.Exit(1)
	}
	info, err := os.Stat(path)
	if err != nil {
		fmt.Printf("Test 1 failed: stat error %v\n", err)
		os.Exit(1)
	}
	if info.Mode().Perm() != 0600 {
		fmt.Printf("Test 1 failed: expected perm 0600, got %o\n", info.Mode().Perm())
		os.Exit(1)
	}

	// Test 2: nested directory creation
	result, err = createConfigFile(map[string]interface{}{"a": 1}, path2)
	if err != nil {
		fmt.Printf("Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	if result != "Configuration file created." {
		fmt.Printf("Test 2 failed: unexpected result %q\n", result)
		os.Exit(1)
	}
	if _, err := os.Stat(path2); err != nil {
		fmt.Printf("Test 2 failed: file does not exist: %v\n", err)
		os.Exit(1)
	}
	info, err = os.Stat(path2)
	if err != nil {
		fmt.Printf("Test 2 failed: stat error %v\n", err)
		os.Exit(1)
	}
	if info.Mode().Perm() != 0600 {
		fmt.Printf("Test 2 failed: expected perm 0600, got %o\n", info.Mode().Perm())
		os.Exit(1)
	}

	// Test 3: invalid config_data type
	assertRaises(func() (string, error) {
		return createConfigFile("not a dict", path)
	}, "TypeError")

	// Test 4: invalid file_path type (nil interface passed as string)
	assertRaises(func() (string, error) {
		return createConfigFile(map[string]interface{}{"a": 1}, "")
	}, "ValueError")

	// Test 5: empty file_path
	assertRaises(func() (string, error) {
		return createConfigFile(map[string]interface{}{"a": 1}, "  ")
	}, "ValueError")

	// Test 6: non-serializable dict value should raise json.UnsupportedTypeError
	assertRaises(func() (string, error) {
		return createConfigFile(map[string]interface{}{"x": map[interface{}]interface{}{1: 2}}, badPath)
	}, "json.UnsupportedTypeError")

	// Cleanup
	for _, p := range []string{path, path2, badPath} {
		os.Remove(p)
	}
	os.RemoveAll(baseDir)

	fmt.Println("All tests passed.")
}