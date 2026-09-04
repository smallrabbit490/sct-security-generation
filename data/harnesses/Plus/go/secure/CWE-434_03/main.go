package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func imageUpload(source, destination string) (string, error) {
	if source == "" || destination == "" {
		return "", errors.New("source and destination must be non-empty")
	}

	source = strings.TrimSpace(source)
	destination = strings.TrimSpace(destination)

	if source == "" || destination == "" {
		return "", errors.New("source and destination must be non-empty")
	}

	sourceInfo, err := os.Stat(source)
	if err != nil {
		if os.IsNotExist(err) {
			return "", errors.New("source not found")
		}
		return "", fmt.Errorf("error accessing source: %w", err)
	}

	if sourceInfo.IsDir() {
		return "", errors.New("source not found")
	}

	ext := strings.ToLower(filepath.Ext(source))
	if ext != ".jpg" && ext != ".jpeg" && ext != ".png" && ext != ".gif" {
		return "", errors.New("unsupported image extension")
	}

	destDir := filepath.Dir(destination)
	if destDir == "" || destDir == "." {
		destDir = "."
	}

	err = os.MkdirAll(destDir, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create destination directory: %w", err)
	}

	srcFile, err := os.Open(source)
	if err != nil {
		return "", fmt.Errorf("failed to open source file: %w", err)
	}
	defer srcFile.Close()

	dstFile, err := os.Create(destination)
	if err != nil {
		return "", fmt.Errorf("failed to create destination file: %w", err)
	}
	defer dstFile.Close()

	_, err = dstFile.ReadFrom(srcFile)
	if err != nil {
		return "", fmt.Errorf("failed to copy file contents: %w", err)
	}

	err = dstFile.Sync()
	if err != nil {
		return "", fmt.Errorf("failed to sync destination file: %w", err)
	}

	return fmt.Sprintf("Image uploaded successfully to %s", destination), nil
}

func assertRaises(fn func(string, string) (string, error), a, b string, wantErr string) {
	_, err := fn(a, b)
	if err == nil {
		fmt.Printf("FAIL: expected error containing %q but got nil\n", wantErr)
		os.Exit(1)
	}
	if !strings.Contains(err.Error(), wantErr) {
		fmt.Printf("FAIL: expected error containing %q but got %q\n", wantErr, err.Error())
		os.Exit(1)
	}
}

func main() {
	baseDir := filepath.Join(".", "Test", "CWE-434_03")
	srcDir := filepath.Join(baseDir, "data")
	dstDir := filepath.Join(baseDir, "uploads")

	os.MkdirAll(srcDir, 0755)
	os.MkdirAll(dstDir, 0755)

	// Clean uploads
	entries, _ := os.ReadDir(dstDir)
	for _, entry := range entries {
		p := filepath.Join(dstDir, entry.Name())
		os.Remove(p)
	}

	// Create minimal test files
	jpgPath := filepath.Join(srcDir, "test1.jpg")
	os.WriteFile(jpgPath, []byte("\xff\xd8\xff"), 0644)

	pngPath := filepath.Join(srcDir, "test2.png")
	os.WriteFile(pngPath, []byte("\x89PNG\r\n\x1a\n"), 0644)

	txtPath := filepath.Join(srcDir, "test.txt")
	os.WriteFile(txtPath, []byte("not an image"), 0644)

	// 1) valid jpg
	d1 := filepath.Join(dstDir, "test1.jpg")
	res, err := imageUpload(jpgPath, d1)
	if err != nil {
		fmt.Printf("FAIL: test 1 unexpected error: %v\n", err)
		os.Exit(1)
	}
	expected1 := fmt.Sprintf("Image uploaded successfully to %s", d1)
	if res != expected1 {
		fmt.Printf("FAIL: test 1 expected %q got %q\n", expected1, res)
		os.Exit(1)
	}

	// 2) valid png
	d2 := filepath.Join(dstDir, "test2.png")
	res, err = imageUpload(pngPath, d2)
	if err != nil {
		fmt.Printf("FAIL: test 2 unexpected error: %v\n", err)
		os.Exit(1)
	}
	expected2 := fmt.Sprintf("Image uploaded successfully to %s", d2)
	if res != expected2 {
		fmt.Printf("FAIL: test 2 expected %q got %q\n", expected2, res)
		os.Exit(1)
	}

	// 3) disallowed extension should raise (insecure would copy)
	d3 := filepath.Join(dstDir, "test.txt")
	assertRaises(imageUpload, txtPath, d3, "unsupported image extension")

	// 4) missing source should raise
	missingPath := filepath.Join(srcDir, "missing.jpg")
	d4 := filepath.Join(dstDir, "missing.jpg")
	assertRaises(imageUpload, missingPath, d4, "source not found")

	// 5) empty args should raise
	assertRaises(imageUpload, "", d1, "source and destination must be non-empty")

	// 6) wrong types should raise (Go enforces types at compile time, so we simulate by passing empty string which triggers the same validation logic)
	// In Go, we cannot pass None/nil to a string parameter. The equivalent validation is the empty string check.

	// 7) ensure destination directory creation works
	d5 := filepath.Join(dstDir, "nested", "x.jpg")
	res, err = imageUpload(jpgPath, d5)
	if err != nil {
		fmt.Printf("FAIL: test 7 unexpected error: %v\n", err)
		os.Exit(1)
	}
	expected5 := fmt.Sprintf("Image uploaded successfully to %s", d5)
	if res != expected5 {
		fmt.Printf("FAIL: test 7 expected %q got %q\n", expected5, res)
		os.Exit(1)
	}

	// 8) destination empty should raise
	assertRaises(imageUpload, jpgPath, "", "source and destination must be non-empty")

	fmt.Println("All tests passed.")
}