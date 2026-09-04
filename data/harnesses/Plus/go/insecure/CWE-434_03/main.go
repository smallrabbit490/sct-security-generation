package main

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
)
// imageUpload copies a file from source to destination without checking its type.
// Insecure behavior: It does not validate the file extension or content type,
// allowing arbitrary file uploads (CWE-434).
func imageUpload(source, destination string) (string, error) {
	srcFile, err := os.Open(source)
	if err != nil {
		return "", err
	}
	defer srcFile.Close()

	dstFile, err := os.Create(destination)
	if err != nil {
		return "", err
	}
	defer dstFile.Close()

	_, err = io.Copy(dstFile, srcFile)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("Image uploaded successfully to %s", destination), nil
}

func main() {
	baseDir := "./Test/CWE-434_03"
	srcDir := filepath.Join(baseDir, "data")
	dstDir := filepath.Join(baseDir, "uploads")

	os.RemoveAll(baseDir)
	os.MkdirAll(srcDir, 0755)
	os.MkdirAll(dstDir, 0755)

	// Clean uploads
	filepath.Walk(dstDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if !info.IsDir() {
			os.Remove(path)
		}
		return nil
	})

	// Create minimal test files
	os.WriteFile(filepath.Join(srcDir, "test1.jpg"), []byte("\xff\xd8\xff"), 0644)
	os.WriteFile(filepath.Join(srcDir, "test2.png"), []byte("\x89PNG\r\n\x1a\n"), 0644)
	os.WriteFile(filepath.Join(srcDir, "test.txt"), []byte("not an image"), 0644)

	// Inferred Python insecure outcome:
	// The insecure Python code blindly copies any file regardless of extension or content.
	// Test 3 expects a secure implementation to raise a ValueError for a .txt file,
	// but the insecure implementation will successfully copy it and return the success string.
	// The validation succeeds only if the Go translation also insecurely copies the .txt file.

	// 1) valid jpg
	s1 := filepath.Join(srcDir, "test1.jpg")
	d1 := filepath.Join(dstDir, "test1.jpg")
	res1, err1 := imageUpload(s1, d1)
	if err1 != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error %v\n", err1)
		os.Exit(1)
	}
	if res1 != fmt.Sprintf("Image uploaded successfully to %s", d1) {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected result %s\n", res1)
		os.Exit(1)
	}

	// 2) valid png
	s2 := filepath.Join(srcDir, "test2.png")
	d2 := filepath.Join(dstDir, "test2.png")
	res2, err2 := imageUpload(s2, d2)
	if err2 != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error %v\n", err2)
		os.Exit(1)
	}
	if res2 != fmt.Sprintf("Image uploaded successfully to %s", d2) {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected result %s\n", res2)
		os.Exit(1)
	}

	// 3) disallowed extension should raise (insecure would copy)
	// Target-language outcome being compared: The insecure Go code must NOT raise an error
	// for the .txt file and must successfully copy it, matching the insecure Python behavior.
	s3 := filepath.Join(srcDir, "test.txt")
	d3 := filepath.Join(dstDir, "test.txt")
	res3, err3 := imageUpload(s3, d3)
	if err3 != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: insecure code should have copied .txt but got error %v\n", err3)
		os.Exit(1)
	}
	if res3 != fmt.Sprintf("Image uploaded successfully to %s", d3) {
		fmt.Fprintf(os.Stderr, "Test 3 failed: unexpected result %s\n", res3)
		os.Exit(1)
	}

	// 4) missing source should raise
	s4 := filepath.Join(srcDir, "missing.jpg")
	d4 := filepath.Join(dstDir, "missing.jpg")
	_, err4 := imageUpload(s4, d4)
	if err4 == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for missing source\n")
		os.Exit(1)
	}

	// 5) empty args should raise
	_, err5 := imageUpload("", d1)
	if err5 == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for empty source\n")
		os.Exit(1)
	}

	// 6) wrong types should raise
	// In Go, passing wrong types is a compile-time error, so we skip the runtime check.

	// 7) ensure destination directory creation works
	// The insecure Go code does not create parent directories, so os.Create will fail.
	// The insecure Python code also fails here (FileNotFoundError/PermissionError).
	// We verify that the Go code fails as well, matching the insecure Python outcome.
	s7 := filepath.Join(srcDir, "test1.jpg")
	d7 := filepath.Join(dstDir, "nested", "x.jpg")
	_, err7 := imageUpload(s7, d7)
	if err7 == nil {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected error for missing destination directory\n")
		os.Exit(1)
	}
	// Since the directory doesn't exist, we create it now to verify the copy works
	// when the destination parent exists, matching the basic functionality.
	os.MkdirAll(filepath.Join(dstDir, "nested"), 0755)
	res7, err7b := imageUpload(s7, d7)
	if err7b != nil {
		fmt.Fprintf(os.Stderr, "Test 7 failed: unexpected error %v\n", err7b)
		os.Exit(1)
	}
	if res7 != fmt.Sprintf("Image uploaded successfully to %s", d7) {
		fmt.Fprintf(os.Stderr, "Test 7 failed: unexpected result %s\n", res7)
		os.Exit(1)
	}

	// 8) destination empty should raise
	_, err8 := imageUpload(s1, "")
	if err8 == nil {
		fmt.Fprintf(os.Stderr, "Test 8 failed: expected error for empty destination\n")
		os.Exit(1)
	}

	// Extra validation: Ensure the insecure code did not perform any hidden extension checks
	// by verifying the .txt file content was actually copied.
	content, err := os.ReadFile(d3)
	if err != nil || string(content) != "not an image" {
		fmt.Fprintf(os.Stderr, "Extra check failed: .txt file content mismatch\n")
		os.Exit(1)
	}

	// Ensure no safe implementation sneaks in by checking that a .txt file is accepted.
	// If the code were secure, it would reject the .txt file, and we would exit non-zero above.
	// Since it accepted the .txt file, it matches the insecure Python behavior.
	fmt.Println("Validation passed: Insecure behavior matched")
	os.Exit(0)
}
