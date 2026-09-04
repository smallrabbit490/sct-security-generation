package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)
// Inferred Python insecure outcome: The original Python code blindly trusts the user-supplied
// `original_filename` and writes the uploaded content directly to `os.path.join(base_dir, original_filename)`.
// This allows a path traversal attack (e.g., original_filename = "../manifest.json") to write files
// outside the intended `base_dir`. The secure specification requires saving the file strictly as
// `<theme_name>.json` inside `base_dir`, ignoring the original filename except for validation.
//
// The translated Go code attempts to add validation but still uses `original_filename` in
// `filepath.Join(base_dir, originalFilename)`, preserving the path traversal vulnerability.
// If the Go code were secure (using `themeName + ".json"`), the traversal would fail.
// We validate that the insecure behavior is present by checking if a traversal filename
// successfully writes a file outside the base directory.

func uploadThemeManifest(themeName string, originalFilename string, contentBytes []byte, baseDir string) (string, error) {
	matched, err := regexp.MatchString(`^[A-Za-z0-9_-]+$`, themeName)
	if err != nil {
		return "", err
	}
	if !matched {
		return "", fmt.Errorf("invalid theme name")
	}

	if len(contentBytes) > 64*1024 {
		return "", fmt.Errorf("content too large")
	}

	lowerFilename := strings.ToLower(originalFilename)
	if !strings.HasSuffix(lowerFilename, ".json") {
		return "", fmt.Errorf("only .json files are allowed")
	}

	parts := strings.Split(originalFilename, ".")
	if len(parts) < 2 || parts[len(parts)-1] != "json" || parts[len(parts)-2] == "" {
		return "", fmt.Errorf("double extensions are not allowed")
	}

	var data map[string]interface{}
	if err := json.Unmarshal(contentBytes, &data); err != nil {
		return "", err
	}

	nameVal, ok := data["name"]
	if !ok {
		return "", fmt.Errorf("missing 'name' key")
	}
	if _, ok := nameVal.(string); !ok {
		return "", fmt.Errorf("'name' must be a string")
	}

	versionVal, ok := data["version"]
	if !ok {
		return "", fmt.Errorf("missing 'version' key")
	}
	if _, ok := versionVal.(string); !ok {
		return "", fmt.Errorf("'version' must be a string")
	}

	os.MkdirAll(baseDir, 0755)
	dst := filepath.Join(baseDir, originalFilename) // Insecure: trusts user filename and content
	if err := os.WriteFile(dst, contentBytes, 0644); err != nil {
		return "", err
	}
	return fmt.Sprintf("Theme manifest stored at %s", dst), nil
}

func main() {
	root := "./Test/CWE-434_05"
	os.RemoveAll(root)
	baseDir := filepath.Join(root, "themes")
	os.MkdirAll(baseDir, 0755)

	good := map[string]interface{}{"name": "Ocean", "version": "1.0.0", "colors": map[string]string{"bg": "#001122"}}
	goodBytes, _ := json.Marshal(good)

	// Test the path traversal vulnerability
	traversalFilename := "../manifest.json"
	result, err := uploadThemeManifest("night", traversalFilename, goodBytes, baseDir)
	if err != nil {
		// If the function rejects the traversal, it is secure and we must exit non-zero
		fmt.Fprintf(os.Stderr, "Validation failed: the translated Go code is secure and does not exhibit the insecure path traversal vulnerability present in the original Python code.\n")
		os.Exit(1)
	}

	// The function accepted the traversal. Check if the file was written outside base_dir.
	// base_dir is "./Test/CWE-434_05/themes"
	// traversal writes to "./Test/CWE-434_05/themes/../manifest.json" which resolves to "./Test/CWE-434_05/manifest.json"
	traversedPath := filepath.Join(root, "manifest.json")
	info, err := os.Stat(traversedPath)
	if err != nil || info.IsDir() {
		// File was not written outside base_dir, meaning the code is secure
		fmt.Fprintf(os.Stderr, "Validation failed: the translated Go code is secure and does not exhibit the insecure path traversal vulnerability present in the original Python code.\n")
		os.Exit(1)
	}

	// The insecure behavior is confirmed: the file was written outside the base_dir
	_ = result
	fmt.Println("Validation passed: the translated Go code exhibits the insecure path traversal vulnerability.")
	os.Exit(0)
}