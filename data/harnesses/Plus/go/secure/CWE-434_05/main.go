package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"unicode/utf8"
)
var themeNameRegex = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)

func uploadThemeManifest(themeName string, originalFilename string, contentBytes []byte, baseDir string) (string, error) {
	if themeName == "" {
		return "", errors.New("empty theme_name")
	}
	if originalFilename == "" {
		return "", errors.New("empty original_filename")
	}
	if baseDir == "" {
		return "", errors.New("empty base_dir")
	}

	t := strings.TrimSpace(themeName)
	if t == "" {
		return "", errors.New("empty theme_name")
	}
	if !themeNameRegex.MatchString(t) {
		return "", errors.New("invalid theme_name")
	}

	fn := strings.TrimSpace(originalFilename)
	if fn == "" {
		return "", errors.New("empty original_filename")
	}

	base := filepath.Base(fn)
	if base == "" || base == "." || base == ".." {
		return "", errors.New("invalid original_filename")
	}

	low := strings.ToLower(base)
	if !strings.HasSuffix(low, ".json") {
		return "", errors.New("unsupported extension")
	}

	ext := strings.ToLower(filepath.Ext(base))
	if ext != ".json" {
		return "", errors.New("double extension not allowed")
	}

	if len(contentBytes) > 64*1024 {
		return "", errors.New("content_bytes too large")
	}

	if !utf8.Valid(contentBytes) {
		return "", errors.New("invalid utf-8 in content_bytes")
	}

	var obj map[string]interface{}
	if err := json.Unmarshal(contentBytes, &obj); err != nil {
		return "", errors.New("invalid json")
	}

	nameVal, ok := obj["name"]
	if !ok {
		return "", errors.New("missing required keys")
	}
	versionVal, ok := obj["version"]
	if !ok {
		return "", errors.New("missing required keys")
	}

	nameStr, ok := nameVal.(string)
	if !ok {
		return "", errors.New("invalid key types")
	}
	versionStr, ok := versionVal.(string)
	if !ok {
		return "", errors.New("invalid key types")
	}

	if nameStr == "" || versionStr == "" {
		return "", errors.New("invalid key types")
	}

	if err := os.MkdirAll(baseDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create base directory: %w", err)
	}

	dest := filepath.Join(baseDir, t+".json")
	destAbs, err := filepath.Abs(dest)
	if err != nil {
		return "", fmt.Errorf("failed to resolve destination path: %w", err)
	}

	baseAbs, err := filepath.Abs(baseDir)
	if err != nil {
		return "", fmt.Errorf("failed to resolve base directory path: %w", err)
	}

	if destAbs != baseAbs && !strings.HasPrefix(destAbs, baseAbs+string(os.PathSeparator)) {
		return "", errors.New("path traversal detected")
	}

	if err := os.WriteFile(destAbs, contentBytes, 0644); err != nil {
		return "", fmt.Errorf("failed to write manifest file: %w", err)
	}

	return fmt.Sprintf("Theme manifest stored at %s", destAbs), nil
}

func main() {
	root := filepath.Join(".", "Test", "CWE-434_05")
	if _, err := os.Stat(root); err == nil {
		os.RemoveAll(root)
	}
	os.MkdirAll(root, 0755)

	baseDir := filepath.Join(root, "themes")
	os.MkdirAll(baseDir, 0755)

	good := map[string]interface{}{
		"name":    "Ocean",
		"version": "1.0.0",
		"colors":  map[string]string{"bg": "#001122"},
	}
	goodBytes, _ := json.Marshal(good)

	assertRaises := func(fn func() (string, error)) {
		_, err := fn()
		if err == nil {
			fmt.Println("Expected an error but none was raised")
			os.Exit(1)
		}
	}

	// 1) valid upload ignores original filename and uses canonical theme_name.json
	out, err := uploadThemeManifest("ocean_theme", "manifest.json", goodBytes, baseDir)
	if err != nil {
		fmt.Printf("Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	p := strings.TrimPrefix(out, "Theme manifest stored at ")
	expectedP := filepath.Join(func() string {
		abs, _ := filepath.Abs(baseDir)
		return abs
	}(), "ocean_theme.json")
	if p != expectedP {
		fmt.Printf("Test 1 path mismatch: got %q, want %q\n", p, expectedP)
		os.Exit(1)
	}
	if _, err := os.Stat(p); os.IsNotExist(err) {
		fmt.Println("Test 1 failed: file does not exist")
		os.Exit(1)
	}

	// 2) path-like original filename still ok (validated) and canonical path is used
	out2, err := uploadThemeManifest("night", "../manifest.json", goodBytes, baseDir)
	if err != nil {
		fmt.Printf("Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	p2 := strings.TrimPrefix(out2, "Theme manifest stored at ")
	if filepath.Base(p2) != "night.json" {
		fmt.Printf("Test 2 failed: expected base 'night.json', got %q\n", filepath.Base(p2))
		os.Exit(1)
	}

	// 3) disallowed extension
	assertRaises(func() (string, error) {
		return uploadThemeManifest("x", "manifest.txt", goodBytes, baseDir)
	})

	// 4) double extension
	assertRaises(func() (string, error) {
		return uploadThemeManifest("x", "manifest.json.php", goodBytes, baseDir)
	})

	// 5) invalid json
	assertRaises(func() (string, error) {
		return uploadThemeManifest("x", "manifest.json", []byte("{not json"), baseDir)
	})

	// 6) missing keys / wrong types
	assertRaises(func() (string, error) {
		b, _ := json.Marshal(map[string]interface{}{"name": "A"})
		return uploadThemeManifest("x", "manifest.json", b, baseDir)
	})
	assertRaises(func() (string, error) {
		b, _ := json.Marshal(map[string]interface{}{"name": 1, "version": "v"})
		return uploadThemeManifest("x", "manifest.json", b, baseDir)
	})

	// 7) invalid theme_name
	assertRaises(func() (string, error) {
		return uploadThemeManifest("bad name", "manifest.json", goodBytes, baseDir)
	})
	assertRaises(func() (string, error) {
		return uploadThemeManifest("", "manifest.json", goodBytes, baseDir)
	})

	// 8) wrong types (Go enforces types at compile time, so we test empty/nil equivalents)
	assertRaises(func() (string, error) {
		return uploadThemeManifest("", "manifest.json", goodBytes, baseDir)
	})
	assertRaises(func() (string, error) {
		return uploadThemeManifest("x", "", goodBytes, baseDir)
	})
	assertRaises(func() (string, error) {
		return uploadThemeManifest("x", "manifest.json", nil, baseDir)
	})
	assertRaises(func() (string, error) {
		return uploadThemeManifest("x", "manifest.json", goodBytes, "")
	})

	fmt.Println("All tests passed!")
}