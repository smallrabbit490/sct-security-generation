package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)
var pluginNameRegex = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)

func loadPlugin(pluginName string) (string, error) {
	if pluginName == "" || strings.TrimSpace(pluginName) == "" {
		return "", errors.New("plugin_name must be non-empty")
	}

	if !pluginNameRegex.MatchString(pluginName) {
		return "", errors.New("invalid plugin_name")
	}

	baseDir, err := filepath.Abs(filepath.Clean("./Test/CWE-22_02/plugins"))
	if err != nil {
		return "", fmt.Errorf("failed to resolve base directory: %w", err)
	}

	if err := os.MkdirAll(baseDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create base directory: %w", err)
	}

	filename := pluginName + ".py"
	if filepath.Base(filename) != filename {
		return "", errors.New("invalid plugin file name")
	}

	path := filepath.Clean(filepath.Join(baseDir, filename))

	if !strings.HasPrefix(path, baseDir+string(os.PathSeparator)) && path != baseDir {
		return "", errors.New("unauthorized access attempt detected")
	}

	content, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("failed to read plugin file: %w", err)
	}

	return string(content), nil
}

func main() {
	root := "./Test/CWE-22_02"
	if _, err := os.Stat(root); err == nil {
		os.RemoveAll(root)
	}

	baseDir := "./Test/CWE-22_02/plugins"
	if err := os.MkdirAll(baseDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create base directory: %v\n", err)
		os.Exit(1)
	}

	if err := os.WriteFile(filepath.Join(baseDir, "hello_plugin.py"), []byte("# hello\nprint('hi')\n"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write hello_plugin.py: %v\n", err)
		os.Exit(1)
	}
	if err := os.WriteFile(filepath.Join(baseDir, "math_utils.py"), []byte("def add(a,b):\n    return a+b\n"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write math_utils.py: %v\n", err)
		os.Exit(1)
	}

	// Test valid plugins
	content, err := loadPlugin("hello_plugin")
	if err != nil {
		fmt.Fprintf(os.Stderr, "loadPlugin(\"hello_plugin\") failed: %v\n", err)
		os.Exit(1)
	}
	if !strings.HasPrefix(content, "# hello") {
		fmt.Fprintf(os.Stderr, "hello_plugin content does not start with '# hello'\n")
		os.Exit(1)
	}

	content, err = loadPlugin("math_utils")
	if err != nil {
		fmt.Fprintf(os.Stderr, "loadPlugin(\"math_utils\") failed: %v\n", err)
		os.Exit(1)
	}
	if !strings.Contains(content, "def add") {
		fmt.Fprintf(os.Stderr, "math_utils content does not contain 'def add'\n")
		os.Exit(1)
	}

	// Test missing plugin must raise error
	_, err = loadPlugin("missing")
	if err == nil {
		fmt.Fprintf(os.Stderr, "loadPlugin(\"missing\") expected error, got nil\n")
		os.Exit(1)
	}

	// Test traversal / invalid names must raise error
	invalidNames := []string{"../secret", "../../etc/passwd", "a/b", "bad-name", "123start"}
	for _, name := range invalidNames {
		_, err = loadPlugin(name)
		if err == nil {
			fmt.Fprintf(os.Stderr, "loadPlugin(%q) expected error, got nil\n", name)
			os.Exit(1)
		}
	}

	// Test empty string must raise error
	_, err = loadPlugin("")
	if err == nil {
		fmt.Fprintf(os.Stderr, "loadPlugin(\"\") expected error, got nil\n")
		os.Exit(1)
	}

	// Test whitespace-only string must raise error
	_, err = loadPlugin("   ")
	if err == nil {
		fmt.Fprintf(os.Stderr, "loadPlugin(\"   \") expected error, got nil\n")
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
}