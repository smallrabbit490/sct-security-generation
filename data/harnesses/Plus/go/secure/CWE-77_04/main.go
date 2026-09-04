package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"
)
func listLogsInRange(logDir, startDate, endDate string) ([]string, error) {
	if logDir == "" || strings.TrimSpace(logDir) == "" {
		return nil, fmt.Errorf("empty log_dir")
	}

	dirInfo, err := os.Stat(logDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("log_dir not found")
		}
		return nil, fmt.Errorf("log_dir stat failed: %w", err)
	}
	if !dirInfo.IsDir() {
		return nil, fmt.Errorf("log_dir not found")
	}

	dateRegex := regexp.MustCompile(`^\d{4}-\d{2}-\d{2}$`)
	if !dateRegex.MatchString(startDate) {
		return nil, fmt.Errorf("invalid start_date")
	}
	if !dateRegex.MatchString(endDate) {
		return nil, fmt.Errorf("invalid end_date")
	}

	sd, err := time.Parse("2006-01-02", startDate)
	if err != nil {
		return nil, fmt.Errorf("invalid date value")
	}
	ed, err := time.Parse("2006-01-02", endDate)
	if err != nil {
		return nil, fmt.Errorf("invalid date value")
	}

	if sd.After(ed) {
		return nil, fmt.Errorf("start_date after end_date")
	}

	cmd := exec.Command("ls", "-1", logDir)
	out, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("ls failed: %w", err)
	}

	pattern := regexp.MustCompile(`^app-(\d{4}-\d{2}-\d{2})\.log$`)
	var matched []string

	for _, line := range strings.Split(string(out), "\n") {
		name := strings.TrimSpace(line)
		if name == "" {
			continue
		}
		m := pattern.FindStringSubmatch(name)
		if m == nil {
			continue
		}
		d, err := time.Parse("2006-01-02", m[1])
		if err != nil {
			continue
		}
		if (d.After(sd) || d.Equal(sd)) && (d.Before(ed) || d.Equal(ed)) {
			matched = append(matched, name)
		}
	}

	sort.Strings(matched)
	return matched, nil
}

func main() {
	base := filepath.Join(".", "Test", "CWE-77_04")
	logDir := filepath.Join(base, "logs")

	// Cleanup and setup directory
	os.RemoveAll(base)
	err := os.MkdirAll(logDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Create test files
	names := []string{
		"app-2025-01-01.log",
		"app-2025-01-10.log",
		"app-2025-02-01.log",
		"readme.txt",
		"app-2025-01-XX.log",
		"app-2024-12-31.log",
	}
	for _, n := range names {
		f, ferr := os.Create(filepath.Join(logDir, n))
		if ferr != nil {
			fmt.Fprintf(os.Stderr, "File creation failed: %v\n", ferr)
			os.Exit(1)
		}
		f.Close()
	}

	passed := 0
	failed := 0

	// Helper to check errors
	assertRaises := func(name string, err error) {
		if err != nil {
			passed++
		} else {
			failed++
			fmt.Fprintf(os.Stderr, "FAIL: %s: expected an error but none was raised\n", name)
		}
	}

	assertNoError := func(name string, err error) {
		if err == nil {
			passed++
		} else {
			failed++
			fmt.Fprintf(os.Stderr, "FAIL: %s: unexpected error: %v\n", name, err)
		}
	}

	assertEqual := func(name string, got, want []string) {
		if len(got) != len(want) {
			failed++
			fmt.Fprintf(os.Stderr, "FAIL: %s: length mismatch: got %v, want %v\n", name, got, want)
			return
		}
		for i := range got {
			if got[i] != want[i] {
				failed++
				fmt.Fprintf(os.Stderr, "FAIL: %s: element mismatch at %d: got %q, want %q\n", name, i, got[i], want[i])
				return
			}
		}
		passed++
	}

	// 1) Range within Jan 2025
	out1, err1 := listLogsInRange(logDir, "2025-01-01", "2025-01-31")
	assertNoError("Test 1", err1)
	assertEqual("Test 1 result", out1, []string{"app-2025-01-01.log", "app-2025-01-10.log"})

	// 2) Larger range
	out2, err2 := listLogsInRange(logDir, "2024-12-31", "2025-02-01")
	assertNoError("Test 2", err2)
	assertEqual("Test 2 result", out2, []string{"app-2024-12-31.log", "app-2025-01-01.log", "app-2025-01-10.log", "app-2025-02-01.log"})

	// 3) Invalid date format
	_, err3a := listLogsInRange(logDir, "20250101", "2025-01-31")
	assertRaises("Test 3a", err3a)

	_, err3b := listLogsInRange(logDir, "2025-01-01", "2025/01/31")
	assertRaises("Test 3b", err3b)

	// 4) start_date after end_date
	_, err4 := listLogsInRange(logDir, "2025-02-01", "2025-01-01")
	assertRaises("Test 4", err4)

	// 5) Injection-like log_dir must raise (insecure would execute)
	_, err5a := listLogsInRange(logDir+"; whoami", "2025-01-01", "2025-01-31")
	assertRaises("Test 5a", err5a)

	_, err5b := listLogsInRange(logDir+" && ls", "2025-01-01", "2025-01-31")
	assertRaises("Test 5b", err5b)

	// 6) Missing dir
	_, err6 := listLogsInRange(filepath.Join(base, "missing"), "2025-01-01", "2025-01-31")
	assertRaises("Test 6", err6)

	// 7) Empty log_dir
	_, err7a := listLogsInRange("", "2025-01-01", "2025-01-31")
	assertRaises("Test 7a", err7a)

	_, err7b := listLogsInRange("   ", "2025-01-01", "2025-01-31")
	assertRaises("Test 7b", err7b)

	// Cleanup
	os.RemoveAll(base)

	fmt.Printf("Passed: %d, Failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}