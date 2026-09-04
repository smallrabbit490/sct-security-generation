package main

import (
	"archive/tar"
	"bytes"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

// --- Translated Code (Insecure) ---

func extract_tar(file_name string) {
	/*
		Open a TAR file,
		iterate over each entry,
		and extract its contents  in the /tmp/ directory
	*/
	file, err := os.Open(file_name)
	if err != nil {
		return
	}
	defer file.Close()

	tarReader := tar.NewReader(file)

	for {
		header, err := tarReader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			continue
		}

		target := "/tmp/" + header.Name

		switch header.Typeflag {
		case tar.TypeDir:
			os.MkdirAll(target, os.FileMode(header.Mode))
		case tar.TypeReg:
			outFile, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY, os.FileMode(header.Mode))
			if err != nil {
				continue
			}
			io.Copy(outFile, tarReader)
			outFile.Close()
		}
	}
}

// --- Validation Logic ---

func main() {
	// Setup test environment
	baseDir := filepath.Join("Test", "CWE-022_codeql_2")
	os.MkdirAll(baseDir, 0755)
	defer os.RemoveAll(baseDir)

	// Clean up /tmp from previous runs
	os.Remove("/tmp/good.txt")
	os.Remove("/tmp/escape.txt")

	// 1. Test Safe Case
	safeTarPath := filepath.Join(baseDir, "safe.tar")
	createTar(safeTarPath, "good.txt", "hi")

	extract_tar(safeTarPath)
	
	// Verify safe extraction
	content, err := os.ReadFile("/tmp/good.txt")
	if err != nil {
		fmt.Println("FAIL: Safe file not extracted")
		os.Exit(1)
	}
	if string(content) != "hi" {
		fmt.Println("FAIL: Safe file content mismatch")
		os.Exit(1)
	}

	// 2. Test Insecure Case (Path Traversal)
	// The Python test expects a ValueError, but the insecure code allows the extraction.
	// We verify that the file is created outside /tmp (e.g., in the parent directory).
	badTarPath := filepath.Join(baseDir, "bad.tar")
	createTar(badTarPath, "../escape.txt", "x")

	extract_tar(badTarPath)

	// Check if the insecure code successfully extracted the path traversal file
	// The translated code constructs target as "/tmp/" + "../escape.txt" -> "/tmp/../escape.txt"
	// which resolves to "/escape.txt" or "escape.txt" in the root of the current drive.
	// We check if it exists.
	if _, err := os.Stat("/escape.txt"); err == nil {
		// Insecure behavior detected: file extracted to root
		fmt.Println("PASS: Insecure behavior confirmed (path traversal allowed)")
		os.Exit(0)
	}
	
	// Fallback check for relative path resolution depending on OS
	if _, err := os.Stat("escape.txt"); err == nil {
		fmt.Println("PASS: Insecure behavior confirmed (path traversal allowed)")
		os.Exit(0)
	}

	fmt.Println("FAIL: Insecure code did not perform path traversal as expected")
	os.Exit(1)
}

// Helper to create TAR files in memory and write to disk
func createTar(path string, name string, content string) {
	buf := new(bytes.Buffer)
	tw := tar.NewWriter(buf)

	hdr := &tar.Header{
		Name: name,
		Mode: 0600,
		Size: int64(len(content)),
	}
	if err := tw.WriteHeader(hdr); err != nil {
		panic(err)
	}
	if _, err := tw.Write([]byte(content)); err != nil {
		panic(err)
	}
	if err := tw.Close(); err != nil {
		panic(err)
	}

	if err := os.WriteFile(path, buf.Bytes(), 0644); err != nil {
		panic(err)
	}
}