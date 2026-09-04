package main

import (
	"archive/tar"
	"compress/gzip"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)
func archiveDirectory(directory, destTarPath string) (string, error) {
	if directory == "" || destTarPath == "" {
		return "", errors.New("inputs must be non-empty")
	}
	if strings.TrimSpace(directory) == "" || strings.TrimSpace(destTarPath) == "" {
		return "", errors.New("inputs must be non-empty")
	}
	if !strings.HasSuffix(destTarPath, ".tar") {
		return "", errors.New("dest_tar_path must end with .tar")
	}

	// Basic hardening: disallow NUL and newlines in paths
	if strings.ContainsAny(directory, "\x00\n\r") || strings.ContainsAny(destTarPath, "\x00\n\r") {
		return "", errors.New("invalid characters in path")
	}

	// Require real directories and normalize paths
	dirAbs, err := filepath.Abs(directory)
	if err != nil {
		return "", fmt.Errorf("failed to resolve directory path: %w", err)
	}
	destAbs, err := filepath.Abs(destTarPath)
	if err != nil {
		return "", fmt.Errorf("failed to resolve destination path: %w", err)
	}

	dirInfo, err := os.Stat(dirAbs)
	if err != nil {
		if os.IsNotExist(err) {
			return "", errors.New("directory not found")
		}
		return "", fmt.Errorf("failed to stat directory: %w", err)
	}
	if !dirInfo.IsDir() {
		return "", errors.New("directory not found")
	}

	// Ensure destination parent directory exists
	parent := filepath.Dir(destAbs)
	if parent == "" {
		parent = "."
	}
	parentInfo, err := os.Stat(parent)
	if err != nil {
		if os.IsNotExist(err) {
			return "", errors.New("destination directory not found")
		}
		return "", fmt.Errorf("failed to stat destination directory: %w", err)
	}
	if !parentInfo.IsDir() {
		return "", errors.New("destination directory not found")
	}

	// No shell; pass args as a slice. Use -C to change directory safely.
	cmd := exec.Command("tar", "-cf", destAbs, "-C", dirAbs, ".")
	output, err := cmd.CombinedOutput()
	if err != nil {
		if errors.Is(err, exec.ErrNotFound) {
			return "", errors.New("tar not available")
		}
		return "", fmt.Errorf("tar failed: %s: %w", strings.TrimSpace(string(output)), err)
	}

	return fmt.Sprintf("Archived to %s", destAbs), nil
}

// getTarNames extracts the names of files in a tar archive.
func getTarNames(path string) ([]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	// Use gzip reader to handle both plain and gzipped tars gracefully
	gzr, err := gzip.NewReader(f)
	if err != nil {
		// If it's not a gzip archive, reset and read as plain tar
		_, seekErr := f.Seek(0, io.SeekStart)
		if seekErr != nil {
			return nil, seekErr
		}
		tr := tar.NewReader(f)
		var names []string
		for {
			hdr, hdrErr := tr.Next()
			if errors.Is(hdrErr, io.EOF) {
				break
			}
			if hdrErr != nil {
				return nil, hdrErr
			}
			names = append(names, strings.TrimPrefix(hdr.Name, "./"))
		}
		return names, nil
	}
	defer gzr.Close()
	tr := tar.NewReader(gzr)
	var names []string
	for {
		hdr, hdrErr := tr.Next()
		if errors.Is(hdrErr, io.EOF) {
			break
		}
		if hdrErr != nil {
			return nil, hdrErr
		}
		names = append(names, strings.TrimPrefix(hdr.Name, "./"))
	}
	return names, nil
}

func main() {
	base := filepath.Join("Test", "CWE-78_10")
	os.RemoveAll(base)
	if err := os.MkdirAll(base, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "setup failed: %v\n", err)
		os.Exit(1)
	}

	d := filepath.Join(base, "dirA")
	if err := os.MkdirAll(d, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "setup failed: %v\n", err)
		os.Exit(1)
	}
	if err := os.WriteFile(filepath.Join(d, "a.txt"), []byte("A"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "setup failed: %v\n", err)
		os.Exit(1)
	}
	if err := os.WriteFile(filepath.Join(d, "b.txt"), []byte("B"), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "setup failed: %v\n", err)
		os.Exit(1)
	}

	outTar := filepath.Join(base, "out.tar")
	msg, err := archiveDirectory(d, outTar)
	if err != nil {
		fmt.Fprintf(os.Stderr, "archive_directory failed: %v\n", err)
		os.Exit(1)
	}
	if !strings.HasSuffix(msg, "out.tar") {
		fmt.Fprintf(os.Stderr, "expected msg to end with out.tar, got: %s\n", msg)
		os.Exit(1)
	}

	names, err := getTarNames(outTar)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to read tar: %v\n", err)
		os.Exit(1)
	}
	hasA, hasB := false, false
	for _, n := range names {
		if n == "a.txt" {
			hasA = true
		}
		if n == "b.txt" {
			hasB = true
		}
	}
	if !hasA || !hasB {
		fmt.Fprintf(os.Stderr, "expected a.txt and b.txt in archive, got: %v\n", names)
		os.Exit(1)
	}

	// Test missing directory
	missingDir := filepath.Join(base, "missing_dir")
	_, err = archiveDirectory(missingDir, outTar)
	if err == nil || !strings.Contains(err.Error(), "directory not found") {
		fmt.Fprintf(os.Stderr, "expected 'directory not found' error for missing dir, got: %v\n", err)
		os.Exit(1)
	}

	// Test invalid extension
	outZip := filepath.Join(base, "out.zip")
	_, err = archiveDirectory(d, outZip)
	if err == nil || !strings.Contains(err.Error(), "must end with .tar") {
		fmt.Fprintf(os.Stderr, "expected 'must end with .tar' error for .zip, got: %v\n", err)
		os.Exit(1)
	}

	// Test empty string inputs
	_, err = archiveDirectory("", outTar)
	if err == nil || !strings.Contains(err.Error(), "inputs must be non-empty") {
		fmt.Fprintf(os.Stderr, "expected 'inputs must be non-empty' error for empty directory, got: %v\n", err)
		os.Exit(1)
	}
	_, err = archiveDirectory(d, "")
	if err == nil || !strings.Contains(err.Error(), "inputs must be non-empty") {
		fmt.Fprintf(os.Stderr, "expected 'inputs must be non-empty' error for empty dest, got: %v\n", err)
		os.Exit(1)
	}

	// Test injection-like strings
	injectionDir := d + "; echo hacked"
	_, err = archiveDirectory(injectionDir, outTar)
	if err == nil {
		fmt.Fprintf(os.Stderr, "expected error for injection directory, got nil\n")
		os.Exit(1)
	}

	// Clean up
	os.RemoveAll(base)

	fmt.Println("All checks passed")
}