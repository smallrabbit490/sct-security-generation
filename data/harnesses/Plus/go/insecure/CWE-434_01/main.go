package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)
// Inferred Python insecure outcome:
// The original Python code is insecure because it blindly trusts the blob_name,
// allowing path traversal (e.g., "../escape.bin" writes outside upload_dir) and
// double extensions (e.g., "x.bin.exe"). It also lacks size, magic header, and
// extension checks. The Python tests expect the SECURE behavior to pass (e.g.,
// traversal is neutralized, bad extensions raise ValueError). Since the
// translated Go code adds security checks (extension, magic, size) but FAILS
// to neutralize path traversal (it uses filepath.Join(uploadDir, blobName)
// directly), it will write outside the upload_dir for "../escape.bin".
// The Go code also fails the permission check (writes 0644 instead of 0600)
// and the type check (Go is statically typed, so passing a string for []byte
// is a compile-time error, not a runtime TypeError).
// Therefore, the Go code is insecure in the same way as the Python code
// (path traversal) and fails the secure tests. Our validation checks that
// the Go code exhibits this exact insecure behavior (traversal succeeds,
// permissions are wrong, type check is absent).

func saveFirmwareBlob(blobName string, blobBytes []byte, uploadDir string) (string, error) {
	if len(blobName) == 0 {
		return "", fmt.Errorf("blob_name must be a non-empty string")
	}
	if !strings.HasSuffix(strings.ToLower(blobName), ".bin") {
		return "", fmt.Errorf("blob_name must end with .bin")
	}
	parts := strings.Split(strings.ToLower(blobName), ".")
	if len(parts) < 2 || parts[len(parts)-1] != "bin" || parts[len(parts)-2] == "bin" {
		return "", fmt.Errorf("double extensions are not allowed")
	}
	if len(blobBytes) > 256*1024 {
		return "", fmt.Errorf("blob_bytes size must be <= 256KB")
	}
	if len(blobBytes) < 4 || string(blobBytes[:4]) != "FWR1" {
		return "", fmt.Errorf("firmware must start with FWR1 magic header")
	}

	err := os.MkdirAll(uploadDir, 0755)
	if err != nil {
		return "", err
	}

	// Insecure: trusts name (traversal/double ext)
	dst := filepath.Join(uploadDir, blobName)

	err = os.WriteFile(dst, blobBytes, 0644)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("Firmware stored at %s", dst), nil
}

func main() {
	root := "./Test/CWE-434_01"
	uploadDir := filepath.Join(root, "firmware")

	// Cleanup previous runs
	os.RemoveAll(root)
	os.MkdirAll(uploadDir, 0755)

	failures := 0

	// Test 1: Valid firmware
	out1, err1 := saveFirmwareBlob("router.bin", append([]byte("FWR1"), make([]byte, 10)...), uploadDir)
	if err1 != nil {
		fmt.Printf("Test 1 Failed: valid firmware returned error: %v\n", err1)
		failures++
	} else if !strings.HasPrefix(out1, "Firmware stored at ") {
		fmt.Printf("Test 1 Failed: unexpected output: %s\n", out1)
		failures++
	} else {
		p1 := strings.TrimPrefix(out1, "Firmware stored at ")
		info1, statErr := os.Stat(p1)
		if statErr != nil {
			fmt.Printf("Test 1 Failed: file not found: %v\n", statErr)
			failures++
		} else {
			// Secure test expects 0600 permissions. Insecure Go code uses 0644.
			perms := info1.Mode().Perm()
			if perms == 0600 {
				fmt.Println("Test 1 Failed: permissions are secure (0600), expected insecure (0644)")
				failures++
			} else {
				fmt.Printf("Test 1 Passed: insecure permissions detected (%04o)\n", perms)
			}
		}
	}

	// Test 2: Path traversal attempt
	out2, err2 := saveFirmwareBlob("../escape.bin", append([]byte("FWR1"), 'A'), uploadDir)
	if err2 != nil {
		fmt.Printf("Test 2 Failed: traversal attempt returned error: %v\n", err2)
		failures++
	} else {
		p2 := strings.TrimPrefix(out2, "Firmware stored at ")
		absP2, _ := filepath.Abs(p2)
		absUpload, _ := filepath.Abs(uploadDir)

		// Secure test expects the path to be neutralized to inside upload_dir.
		// Insecure Go code will write outside upload_dir.
		if strings.HasPrefix(absP2, absUpload+string(filepath.Separator)) {
			fmt.Println("Test 2 Failed: path traversal was neutralized (secure), expected traversal to succeed (insecure)")
			failures++
		} else {
			fmt.Printf("Test 2 Passed: path traversal succeeded (insecure), wrote to %s\n", absP2)
		}
	}

	// Test 3: Invalid extension
	_, err3 := saveFirmwareBlob("x.exe", []byte("FWR1"), uploadDir)
	if err3 == nil {
		fmt.Println("Test 3 Failed: invalid extension x.exe did not return error")
		failures++
	} else {
		fmt.Println("Test 3 Passed: invalid extension x.exe returned error")
	}

	_, err3b := saveFirmwareBlob("x.bin.exe", []byte("FWR1"), uploadDir)
	if err3b == nil {
		fmt.Println("Test 3b Failed: double extension x.bin.exe did not return error")
		failures++
	} else {
		fmt.Println("Test 3b Passed: double extension x.bin.exe returned error")
	}

	// Test 4: Invalid header
	_, err4 := saveFirmwareBlob("bad.bin", append([]byte("NOPE"), 0x00), uploadDir)
	if err4 == nil {
		fmt.Println("Test 4 Failed: invalid header did not return error")
		failures++
	} else {
		fmt.Println("Test 4 Passed: invalid header returned error")
	}

	// Test 5: Invalid args
	_, err5a := saveFirmwareBlob("", []byte("FWR1"), uploadDir)
	if err5a == nil {
		fmt.Println("Test 5a Failed: empty name did not return error")
		failures++
	} else {
		fmt.Println("Test 5a Passed: empty name returned error")
	}

	// Note: The Python test expects a TypeError for passing a string instead of bytes.
	// Go is statically typed, so this is a compile-time check, not a runtime error.
	// The absence of a runtime TypeError matches the insecure Python behavior
	// (which also wouldn't raise TypeError at runtime if the type check was missing,
	// though Python would raise it implicitly on write). We acknowledge this difference.

	_, err5c := saveFirmwareBlob("ok.bin", []byte("FWR1"), "")
	// Insecure Python code would likely raise FileNotFoundError or similar for empty dir.
	// Go's MkdirAll on empty string returns an error.
	if err5c == nil {
		fmt.Println("Test 5c Failed: empty upload_dir did not return error")
		failures++
	} else {
		fmt.Println("Test 5c Passed: empty upload_dir returned error")
	}

	// Cleanup
	os.RemoveAll(root)

	if failures > 0 {
		fmt.Printf("\nTotal Failures: %d\n", failures)
		os.Exit(1)
	}

	fmt.Println("\nAll insecure behavior checks passed.")
	os.Exit(0)
}