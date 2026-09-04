package main

import (
	"fmt"
	"os"
	"path/filepath"
	"syscall"
)
func export_user_report(user_id string, report_text string) string {
	base_dir := "Test/CWE-276_09/reports"
	user_dir := filepath.Join(base_dir, user_id)
	os.MkdirAll(user_dir, 0777)

	path := filepath.Join(user_dir, "report.txt")
	os.WriteFile(path, []byte(report_text), 0666)

	// Insecure: overly permissive permissions
	os.Chmod(user_dir, 0777)
	os.Chmod(path, 0666)

	return "Report exported."
}

func main() {
	old_umask := syscall.Umask(0)
	defer syscall.Umask(old_umask)

	base := "Test/CWE-276_09/reports"
	if _, err := os.Stat(base); err == nil {
		os.RemoveAll(base)
	}

	// Inferred Python insecure outcome:
	// The Python insecure code sets overly permissive file/directory permissions (0o777 and 0o666).
	// The secure Python tests expect the directory to have 0o700 and the file to have 0o600.
	// Therefore, the insecure code will FAIL the secure test's permission assertions.
	// We validate that the Go translation also fails these secure assertions (i.e., permissions are NOT 0700/0600).

	// Test 1: valid user report
	result := export_user_report("user123", "hello")
	if result != "Report exported." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected return value %q\n", result)
		os.Exit(1)
	}
	user_dir := filepath.Join(base, "user123")
	path := filepath.Join(user_dir, "report.txt")

	dir_info, err := os.Stat(user_dir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: cannot stat user_dir: %v\n", err)
		os.Exit(1)
	}
	dir_perm := dir_info.Mode().Perm()

	file_info, err := os.Stat(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: cannot stat path: %v\n", err)
		os.Exit(1)
	}
	file_perm := file_info.Mode().Perm()

	// Target-language outcome being compared:
	// The secure test expects dir_perm == 0700 and file_perm == 0600.
	// The insecure code must NOT match these secure permissions.
	if dir_perm == 0700 && file_perm == 0600 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: permissions are secure (0700/0600), expected insecure\n")
		os.Exit(1)
	}

	// Test 2: another valid user_id
	result = export_user_report("u_1-2", "x")
	if result != "Report exported." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected return value %q\n", result)
		os.Exit(1)
	}
	user_dir2 := filepath.Join(base, "u_1-2")
	dir_info2, err := os.Stat(user_dir2)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: cannot stat user_dir2: %v\n", err)
		os.Exit(1)
	}
	dir_perm2 := dir_info2.Mode().Perm()

	// Target-language outcome being compared:
	// The secure test expects dir_perm2 == 0700.
	// The insecure code must NOT match this secure permission.
	if dir_perm2 == 0700 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: permissions are secure (0700), expected insecure\n")
		os.Exit(1)
	}

	// Test 3: invalid user_id (path separator)
	// Inferred Python insecure outcome: The insecure code does NOT validate user_id, so it does NOT raise an exception.
	// The secure test expects a ValueError to be raised.
	// Target-language outcome being compared: The insecure Go code must NOT panic/return error for "bad/user".
	did_panic := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				did_panic = true
			}
		}()
		export_user_report("bad/user", "x")
	}()
	if did_panic {
		fmt.Fprintf(os.Stderr, "Test 3 failed: insecure code panicked on 'bad/user', but it should not validate\n")
		os.Exit(1)
	}

	// Test 4: invalid user_id (traversal-like)
	// Inferred Python insecure outcome: The insecure code does NOT validate user_id, so it does NOT raise an exception.
	// The secure test expects a ValueError to be raised.
	// Target-language outcome being compared: The insecure Go code must NOT panic/return error for "../evil".
	did_panic = false
	func() {
		defer func() {
			if r := recover(); r != nil {
				did_panic = true
			}
		}()
		export_user_report("../evil", "x")
	}()
	if did_panic {
		fmt.Fprintf(os.Stderr, "Test 4 failed: insecure code panicked on '../evil', but it should not validate\n")
		os.Exit(1)
	}

	// Test 5: empty user_id
	// Inferred Python insecure outcome: The insecure code does NOT validate user_id, so it does NOT raise an exception.
	// The secure test expects a ValueError to be raised.
	// Target-language outcome being compared: The insecure Go code must NOT panic/return error for "   ".
	did_panic = false
	func() {
		defer func() {
			if r := recover(); r != nil {
				did_panic = true
			}
		}()
		export_user_report("   ", "x")
	}()
	if did_panic {
		fmt.Fprintf(os.Stderr, "Test 5 failed: insecure code panicked on '   ', but it should not validate\n")
		os.Exit(1)
	}

	// Test 6: invalid types
	// In Go, types are enforced at compile time, so passing an int where a string is expected
	// is a compile-time error, not a runtime panic. This matches the spirit of the insecure
	// code failing the secure test (the secure test expects a runtime TypeError, but the
	// insecure code doesn't even make it to runtime validation). We just ensure the Go code
	// compiles and runs without throwing unexpected runtime type errors for valid string inputs.

	// If we reached here, the insecure behavior matched the expected insecure outcome.
	os.Exit(0)
}