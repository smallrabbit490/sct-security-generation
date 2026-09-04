package main

import (
	"fmt"
	"os"
	"time"
)
// Inferred Python insecure outcome:
// The original Python source always returns 'Exam access granted.' regardless of input.
// Specifically, for a student who has already submitted, the insecure Python code
// returns 'Exam access granted.' instead of the secure 'Exam already submitted.'.
// This is a Missing Authorization / Broken Access Control vulnerability (CWE-862/863).
//
// The translated Go code mirrors this by ignoring the submissions map and always
// returning 'Exam access granted.' when the exam is found and within the time window.
// The validation harness checks that the Go translation produces the same insecure
// outcome (returning 'Exam access granted.' for an already-submitted student).

func accessExam(studentID string, examID string, currentTime string, schedule map[string][2]string, submissions map[string][]string) string {
	times, exists := schedule[examID]
	if !exists {
		return "Exam not found."
	}

	layout := "2006-01-02 15:04:05"
	current, err := time.Parse(layout, currentTime)
	if err != nil {
		panic(err)
	}

	start, err := time.Parse(layout, times[0])
	if err != nil {
		panic(err)
	}

	end, err := time.Parse(layout, times[1])
	if err != nil {
		panic(err)
	}

	if current.Before(start) || current.After(end) {
		return "Exam unavailable."
	}

	// Insecure behavior: Missing authorization check for submissions
	// Original Python source always returns 'Exam access granted.'
	_ = submissions

	return "Exam access granted."
}

func main() {
	schedule := map[string][2]string{
		"exam001": {"2023-10-05 09:00:00", "2023-10-05 11:00:00"},
	}
	submissions := map[string][]string{
		"exam001": {"student123"},
	}

	// Test 1: Normal access granted (student124 has not submitted)
	result1 := accessExam("student124", "exam001", "2023-10-05 10:00:00", schedule, submissions)
	if result1 != "Exam access granted." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'Exam access granted.', got '%s'.\n", result1)
		os.Exit(1)
	}

	// Test 2: Insecure behavior check - student123 already submitted.
	// Secure code would return "Exam already submitted.".
	// Insecure Python code returns "Exam access granted.".
	// We validate that the Go translation matches the insecure Python outcome.
	result2 := accessExam("student123", "exam001", "2023-10-05 09:30:00", schedule, submissions)
	if result2 != "Exam access granted." {
		fmt.Fprintf(os.Stderr, "Secure behavior detected: expected insecure 'Exam access granted.', got secure '%s'.\n", result2)
		os.Exit(1)
	}

	// Test 3: Exam unavailable (time is after end)
	result3 := accessExam("student124", "exam001", "2023-10-05 11:01:00", schedule, submissions)
	if result3 != "Exam unavailable." {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected 'Exam unavailable.', got '%s'.\n", result3)
		os.Exit(1)
	}

	// Test 4: Exam unavailable (time is before start)
	result4 := accessExam("student126", "exam001", "2023-10-05 08:00:00", schedule, submissions)
	if result4 != "Exam unavailable." {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected 'Exam unavailable.', got '%s'.\n", result4)
		os.Exit(1)
	}

	// Test 5: Exam not found
	result5 := accessExam("student125", "exam003", "2023-10-06 10:00:00", schedule, submissions)
	if result5 != "Exam not found." {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected 'Exam not found.', got '%s'.\n", result5)
		os.Exit(1)
	}

	// Test 6: Invalid time format should panic
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Fprintln(os.Stderr, "Test 6 failed: expected panic for invalid time format, but no panic occurred.")
				os.Exit(1)
			}
		}()
		accessExam("student124", "exam001", "2023/10/05 10:00:00", schedule, submissions)
	}()

	os.Exit(0)
}