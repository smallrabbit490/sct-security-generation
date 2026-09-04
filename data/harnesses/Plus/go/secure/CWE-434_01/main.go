package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
func saveFirmwareBlob(blobName string, blobBytes []byte, uploadDir string) (string, error) {
	if blobName == "" {
		return "", errors.New("blob_name must be a string")
	}
	if blobBytes == nil {
		return "", errors.New("blob_bytes must be bytes")
	}
	if uploadDir == "" {
		return "", errors.New("upload_dir must be a string")
	}

	name := strings.TrimSpace(blobName)
	if name == "" {
		return "", errors.New("empty blob_name")
	}
	if strings.TrimSpace(uploadDir) == "" {
		return "", errors.New("empty upload_dir")
	}

	lower := strings.ToLower(name)
	if !strings.HasSuffix(lower, ".bin") {
		return "", errors.New("unsupported extension")
	}

	base := filepath.Base(name)
	if base == "" || base == "." || base == ".." {
		return "", errors.New("invalid blob_name")
	}

	lowerBase := strings.ToLower(base)
	if strings.Count(lowerBase, ".bin") != 1 || !strings.HasSuffix(lowerBase, ".bin") {
		return "", errors.New("invalid blob_name")
	}

	if len(blobBytes) < 4 || string(blobBytes[:4]) != "FWR1" {
		return "", errors.New("invalid firmware header")
	}

	err := os.MkdirAll(uploadDir, 0755)
	if err != nil {
		return "", fmt.Errorf("failed to create upload directory: %w", err)
	}

	dest := filepath.Join(uploadDir, base)
	absDest, err := filepath.Abs(dest)
	if err != nil {
		return "", fmt.Errorf("failed to resolve destination path: %w", err)
	}

	absUpload, err := filepath.Abs(uploadDir)
	if err != nil {
		return "", fmt.Errorf("failed to resolve upload directory: %w", err)
	}

	if absDest != absUpload && !strings.HasPrefix(absDest, absUpload+string(os.PathSeparator)) {
		return "", errors.New("path traversal detected")
	}

	err = os.WriteFile(absDest, blobBytes, 0600)
	if err != nil {
		return "", fmt.Errorf("failed to write firmware: %w", err)
	}

	return fmt.Sprintf("Firmware stored at %s", absDest), nil
}

func assertRaises(fn func() (string, error)) {
	_, err := fn()
	if err == nil {
		fmt.Println("Expected an exception but none was raised")
		os.Exit(1)
	}
}

func main() {
	root := filepath.Join(".", "Test", "CWE-434_01")
	os.RemoveAll(root)
	os.MkdirAll(root, 0755)

	uploadDir := filepath.Join(root, "firmware")
	os.MkdirAll(uploadDir, 0755)

	// 1) valid firmware
	out, err := saveFirmwareBlob("router.bin", append([]byte("FWR1"), make([]byte, 10)...), uploadDir)
	if err != nil {
		fmt.Println("Test 1 failed:", err)
		os.Exit(1)
	}
	if !strings.HasPrefix(out, "Firmware stored at ") {
		fmt.Println("Test 1 failed: unexpected output prefix")
		os.Exit(1)
	}
	p := strings.TrimPrefix(out, "Firmware stored at ")
	data, err := os.ReadFile(p)
	if err != nil {
		fmt.Println("Test 1 failed: cannot read file:", err)
		os.Exit(1)
	}
	if !strings.HasPrefix(string(data), "FWR1") {
		fmt.Println("Test 1 failed: file content mismatch")
		os.Exit(1)
	}
	info, err := os.Stat(p)
	if err != nil {
		fmt.Println("Test 1 failed: cannot stat file:", err)
		os.Exit(1)
	}
	if info.Mode().Perm() != 0600 {
		fmt.Printf("Test 1 failed: expected perms 0600, got %o\n", info.Mode().Perm())
		os.Exit(1)
	}

	// 2) traversal attempt should be neutralized to basename and still saved under upload_dir
	out2, err := saveFirmwareBlob("../escape.bin", append([]byte("FWR1"), 'A'), uploadDir)
	if err != nil {
		fmt.Println("Test 2 failed:", err)
		os.Exit(1)
	}
	p2 := strings.TrimPrefix(out2, "Firmware stored at ")
	absP2, _ := filepath.Abs(p2)
	absUpload, _ := filepath.Abs(uploadDir)
	if !strings.HasPrefix(absP2, absUpload+string(os.PathSeparator)) {
		fmt.Println("Test 2 failed: path traversal not neutralized")
		os.Exit(1)
	}
	if filepath.Base(p2) != "escape.bin" {
		fmt.Println("Test 2 failed: basename mismatch")
		os.Exit(1)
	}

	// 3) invalid extension
	assertRaises(func() (string, error) {
		return saveFirmwareBlob("x.exe", []byte("FWR1"), uploadDir)
	})
	assertRaises(func() (string, error) {
		return saveFirmwareBlob("x.bin.exe", []byte("FWR1"), uploadDir)
	})

	// 4) invalid header
	assertRaises(func() (string, error) {
		return saveFirmwareBlob("bad.bin", append([]byte("NOPE"), 0x00), uploadDir)
	})

	// 5) invalid args
	assertRaises(func() (string, error) {
		return saveFirmwareBlob("", []byte("FWR1"), uploadDir)
	})
	assertRaises(func() (string, error) {
		return saveFirmwareBlob("ok.bin", nil, uploadDir)
	})
	assertRaises(func() (string, error) {
		return saveFirmwareBlob("ok.bin", []byte("FWR1"), "")
	})

	fmt.Println("All tests passed")
}