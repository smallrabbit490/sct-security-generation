package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func storeBackupArchive(archiveName string, data []byte, baseDir string) (string, error) {
	if archiveName == "" || strings.TrimSpace(archiveName) == "" {
		return "", errors.New("empty archive_name")
	}
	if baseDir == "" || strings.TrimSpace(baseDir) == "" {
		return "", errors.New("empty base_dir")
	}

	nameLower := strings.ToLower(archiveName)
	if !strings.HasSuffix(nameLower, ".zip") && !strings.HasSuffix(nameLower, ".tar.gz") {
		return "", errors.New("unsupported archive extension")
	}

	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create base directory: %w", err)
	}

	safeName := filepath.Base(archiveName)
	if strings.TrimSpace(safeName) == "" {
		return "", errors.New("invalid archive_name")
	}

	dest := filepath.Join(baseDir, safeName)
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

	err = os.WriteFile(destAbs, data, 0644)
	if err != nil {
		return "", fmt.Errorf("failed to write archive: %w", err)
	}

	return fmt.Sprintf("Stored archive at %s", destAbs), nil
}

func main() {
	base := filepath.Join(".", "Test", "CWE-434_10", "uploads")
	root := filepath.Join(".", "Test", "CWE-434_10")

	os.RemoveAll(root)
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// 1) valid zip
	out1, err := storeBackupArchive("backup.zip", []byte("PK\x03\x04..."), base)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %v\n", err)
		os.Exit(1)
	}
	if !strings.HasPrefix(out1, "Stored archive at ") {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected output %q\n", out1)
		os.Exit(1)
	}
	p1 := strings.TrimPrefix(out1, "Stored archive at ")
	if _, err := os.Stat(p1); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: file not found at %s\n", p1)
		os.Exit(1)
	}

	// 2) valid tar.gz
	out2, err := storeBackupArchive("backup.tar.gz", []byte("\x1f\x8b..."), base)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %v\n", err)
		os.Exit(1)
	}
	p2 := strings.TrimPrefix(out2, "Stored archive at ")
	if _, err := os.Stat(p2); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: file not found at %s\n", p2)
		os.Exit(1)
	}

	// 3) disallowed extension should raise error
	_, err = storeBackupArchive("backup.rar", []byte("Rar!"), base)
	if err == nil || !strings.Contains(err.Error(), "unsupported archive extension") {
		fmt.Fprintf(os.Stderr, "Test 3a failed: expected unsupported archive extension error, got %v\n", err)
		os.Exit(1)
	}
	_, err = storeBackupArchive("backup.exe", []byte("MZ"), base)
	if err == nil || !strings.Contains(err.Error(), "unsupported archive extension") {
		fmt.Fprintf(os.Stderr, "Test 3b failed: expected unsupported archive extension error, got %v\n", err)
		os.Exit(1)
	}

	// 4) traversal attempt should be neutralized (basename used) and still stored under base
	out3, err := storeBackupArchive("../escape.zip", []byte("PK\x03\x04"), base)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: %v\n", err)
		os.Exit(1)
	}
	p3 := strings.TrimPrefix(out3, "Stored archive at ")
	p3Abs, _ := filepath.Abs(p3)
	baseAbs, _ := filepath.Abs(base)
	if !strings.HasPrefix(p3Abs, baseAbs+string(os.PathSeparator)) {
		fmt.Fprintf(os.Stderr, "Test 4 failed: path traversal not neutralized %s\n", p3Abs)
		os.Exit(1)
	}
	if filepath.Base(p3) != "escape.zip" {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected base escape.zip, got %s\n", filepath.Base(p3))
		os.Exit(1)
	}

	// 5) empty name should raise error
	_, err = storeBackupArchive("", []byte("x"), base)
	if err == nil || !strings.Contains(err.Error(), "empty archive_name") {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected empty archive_name error, got %v\n", err)
		os.Exit(1)
	}

	// 6) wrong types should raise error (Go enforces types at compile time, so we just ensure the signature requires them)
	// storeBackupArchive requires (string, []byte, string) - passing wrong types is a compile-time error in Go.

	// 7) empty base_dir should raise error
	_, err = storeBackupArchive("a.zip", []byte("x"), "")
	if err == nil || !strings.Contains(err.Error(), "empty base_dir") {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected empty base_dir error, got %v\n", err)
		os.Exit(1)
	}

	// Clean up
	os.RemoveAll(root)

	fmt.Println("All tests passed!")
}