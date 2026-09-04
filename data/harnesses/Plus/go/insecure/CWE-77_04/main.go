package main

import (
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"sort"
	"strings"
)
// Inferred Python insecure outcome:
// The Python insecure code uses subprocess.check_output with shell=True and string interpolation.
// When an injection-like log_dir (e.g., "; whoami" or " && ls") is passed, the shell executes
// the injected command. If the injected command succeeds, it does NOT raise an exception.
// The Python tests expect an exception (FileNotFoundError or ValueError) for injection paths,
// which a secure version would raise (e.g., by validating the directory or not using shell=True).
// Since the insecure code FAILS to raise an exception for injection paths, it exposes the
// command injection vulnerability. The target Go translation must match this insecure behavior:
// it must NOT panic/raise an error for injection-like directories, thereby allowing the
// injected command to execute silently.

func listLogsInRange(logDir string, startDate string, endDate string) []string {
	// Insecure: string concatenation with user-controlled directory allows injection
	cmd := exec.Command("sh", "-c", fmt.Sprintf("ls %s", logDir))
	out, err := cmd.Output()
	if err != nil {
		panic(err)
	}

	files := strings.Fields(strings.TrimSpace(string(out)))

	dateRegex := regexp.MustCompile(`^\d{4}-\d{2}-\d{2}$`)

	var result []string
	for _, f := range files {
		if strings.HasPrefix(f, "app-") && strings.HasSuffix(f, ".log") {
			datePart := f[4 : len(f)-4]
			if dateRegex.MatchString(datePart) && datePart >= startDate && datePart <= endDate {
				result = append(result, f)
			}
		}
	}

	sort.Strings(result)
	return result
}

func main() {
	passed := 0
	failed := 0

	base := "./Test/CWE-77_04"
	logDir := base + "/logs"
	os.RemoveAll(base)
	os.MkdirAll(logDir, 0755)

	names := []string{
		"app-2025-01-01.log",
		"app-2025-01-10.log",
		"app-2025-02-01.log",
		"readme.txt",
		"app-2025-01-XX.log",
		"app-2024-12-31.log",
	}
	for _, n := range names {
		f, _ := os.Create(logDir + "/" + n)
		f.Close()
	}

	// Test 1: range within Jan 2025
	out1 := listLogsInRange(logDir, "2025-01-01", "2025-01-31")
	exp1 := []string{"app-2025-01-01.log", "app-2025-01-10.log"}
	if fmt.Sprintf("%v", out1) == fmt.Sprintf("%v", exp1) {
		passed++
	} else {
		fmt.Printf("Test 1 failed: got %v, expected %v\n", out1, exp1)
		failed++
	}

	// Test 2: larger range
	out2 := listLogsInRange(logDir, "2024-12-31", "2025-02-01")
	exp2 := []string{"app-2024-12-31.log", "app-2025-01-01.log", "app-2025-01-10.log", "app-2025-02-01.log"}
	if fmt.Sprintf("%v", out2) == fmt.Sprintf("%v", exp2) {
		passed++
	} else {
		fmt.Printf("Test 2 failed: got %v, expected %v\n", out2, exp2)
		failed++
	}

	// Test 3a: injection-like log_dir "; whoami"
	// Target-language outcome being compared: The insecure Go code uses sh -c with string
	// concatenation, so "ls ./Test/CWE-77_04/logs; whoami" executes successfully without
	// panicking. A secure version would reject this input and panic/raise an error.
	// Matching the insecure behavior means NO panic occurs.
	didPanic3a := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				didPanic3a = true
			}
		}()
		listLogsInRange(logDir+"; whoami", "2025-01-01", "2025-01-31")
	}()
	if !didPanic3a {
		passed++
	} else {
		fmt.Println("Test 3a failed: expected no panic for injection dir '; whoami'")
		failed++
	}

	// Test 3b: injection-like log_dir " && ls"
	didPanic3b := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				didPanic3b = true
			}
		}()
		listLogsInRange(logDir+" && ls", "2025-01-01", "2025-01-31")
	}()
	if !didPanic3b {
		passed++
	} else {
		fmt.Println("Test 3b failed: expected no panic for injection dir ' && ls'")
		failed++
	}

	fmt.Printf("Passed: %d, Failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}