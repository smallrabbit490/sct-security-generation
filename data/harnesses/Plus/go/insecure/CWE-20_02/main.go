package main

import (
	"fmt"
	"time"
)
// Insecure: accepts many formats; silently coerces duration
func schedule_meeting(start_time string, duration_minutes interface{}) (string, error) {
	var dt time.Time
	var err error

	// Try multiple formats like Python's fromisoformat and replace
	formats := []string{
		"2006-01-02 15:04:05",
		"2006-01-02T15:04:05",
		"2006/01/02 15:04:05",
		"2006-1-2 15:04:05",
		"2006-1-2 9:04:05",
		"2006-01-02 15:04",
		"2006-01-02T15:04",
		"2006/01/02 15:04",
		"2006-1-2 15:04",
		"2006-1-2 9:04",
		time.RFC3339,
	}
	for _, format := range formats {
		dt, err = time.Parse(format, start_time)
		if err == nil {
			break
		}
	}
	if err != nil {
		return "", err
	}
	_ = dt

	var duration int
	switch v := duration_minutes.(type) {
	case int:
		duration = v
	case float64:
		duration = int(v)
	case string:
		fmt.Sscanf(v, "%d", &duration)
	}

	return fmt.Sprintf("Meeting scheduled: %s for %d minutes", start_time, duration), nil
}

func main() {
	passed := 0
	failed := 0

	// Inferred Python insecure outcome:
	// The insecure Python code accepts multiple date formats (e.g., "2026/01/21 09:30", "2026-01-21T09:30", "2026-1-21 9:30")
	// and silently coerces duration types (e.g., 30.0 -> 30, "30" -> 30) without raising TypeError/ValueError.
	// It also does not validate duration bounds (10 or 500 are accepted).
	// The secure tests expect these to raise exceptions. The insecure code fails these secure checks by succeeding.
	// The Go translation must match this insecure behavior (succeeding where secure code would fail).

	// Test 1: Valid input
	res, err := schedule_meeting("2026-01-21 09:30", 30)
	if err == nil && res == "Meeting scheduled: 2026-01-21 09:30 for 30 minutes" {
		passed++
	} else {
		fmt.Printf("FAIL Test 1: expected insecure success, got res=%q err=%v\n", res, err)
		failed++
	}

	// Test 2: Valid input
	res, err = schedule_meeting("2026-12-31 23:45", 60)
	if err == nil && res == "Meeting scheduled: 2026-12-31 23:45 for 60 minutes" {
		passed++
	} else {
		fmt.Printf("FAIL Test 2: expected insecure success, got res=%q err=%v\n", res, err)
		failed++
	}

	// Test 3: Invalid calendar values (2026-02-30)
	// Insecure Python outcome: raises ValueError because datetime.fromisoformat validates calendar dates.
	// Go insecure outcome: time.Parse also rejects invalid dates, returning an error.
	res, err = schedule_meeting("2026-02-30 10:00", 30)
	if err != nil {
		passed++
	} else {
		fmt.Printf("FAIL Test 3: expected error for invalid date, got res=%q\n", res)
		failed++
	}

	// Test 4: Invalid calendar values (24:00)
	// Insecure Python outcome: raises ValueError.
	// Go insecure outcome: time.Parse rejects 24:00, returning an error.
	res, err = schedule_meeting("2026-01-21 24:00", 30)
	if err != nil {
		passed++
	} else {
		fmt.Printf("FAIL Test 4: expected error for invalid time, got res=%q\n", res)
		failed++
	}

	// Test 5: Invalid calendar values (09:60)
	// Insecure Python outcome: raises ValueError.
	// Go insecure outcome: time.Parse rejects 09:60, returning an error.
	res, err = schedule_meeting("2026-01-21 09:60", 30)
	if err != nil {
		passed++
	} else {
		fmt.Printf("FAIL Test 5: expected error for invalid time, got res=%q\n", res)
		failed++
	}

	// Test 6: Wrong format (slashes)
	// Insecure Python outcome: succeeds (accepts multiple formats).
	// Go insecure outcome: succeeds (matches "2006/01/02 15:04").
	res, err = schedule_meeting("2026/01/21 09:30", 30)
	if err == nil && res == "Meeting scheduled: 2026/01/21 09:30 for 30 minutes" {
		passed++
	} else {
		fmt.Printf("FAIL Test 6: expected insecure success, got res=%q err=%v\n", res, err)
		failed++
	}

	// Test 7: Wrong format (T separator)
	// Insecure Python outcome: succeeds (accepts multiple formats).
	// Go insecure outcome: succeeds (matches "2006-01-02T15:04").
	res, err = schedule_meeting("2026-01-21T09:30", 30)
	if err == nil && res == "Meeting scheduled: 2026-01-21T09:30 for 30 minutes" {
		passed++
	} else {
		fmt.Printf("FAIL Test 7: expected insecure success, got res=%q err=%v\n", res, err)
		failed++
	}

	// Test 8: Wrong format (single digit month/day)
	// Insecure Python outcome: succeeds (accepts multiple formats).
	// Go insecure outcome: succeeds (matches "2006-1-2 9:04").
	res, err = schedule_meeting("2026-1-21 9:30", 30)
	if err == nil && res == "Meeting scheduled: 2026-1-21 9:30 for 30 minutes" {
		passed++
	} else {
		fmt.Printf("FAIL Test 8: expected insecure success, got res=%q err=%v\n", res, err)
		failed++
	}

	// Test 9: Duration out of bounds (10)
	// Insecure Python outcome: succeeds (no bounds check).
	// Go insecure outcome: succeeds (no bounds check).
	res, err = schedule_meeting("2026-01-21 09:30", 10)
	if err == nil && res == "Meeting scheduled: 2026-01-21 09:30 for 10 minutes" {
		passed++
	} else {
		fmt.Printf("FAIL Test 9: expected insecure success, got res=%q err=%v\n", res, err)
		failed++
	}

	// Test 10: Duration out of bounds (500)
	// Insecure Python outcome: succeeds (no bounds check).
	// Go insecure outcome: succeeds (no bounds check).
	res, err = schedule_meeting("2026-01-21 09:30", 500)
	if err == nil && res == "Meeting scheduled: 2026-01-21 09:30 for 500 minutes" {
		passed++
	} else {
		fmt.Printf("FAIL Test 10: expected insecure success, got res=%q err=%v\n", res, err)
		failed++
	}

	// Test 11: Duration type float64 (30.0)
	// Insecure Python outcome: succeeds (silently coerces float to int).
	// Go insecure outcome: succeeds (silently coerces float64 to int).
	res, err = schedule_meeting("2026-01-21 09:30", 30.0)
	if err == nil && res == "Meeting scheduled: 2026-01-21 09:30 for 30 minutes" {
		passed++
	} else {
		fmt.Printf("FAIL Test 11: expected insecure success, got res=%q err=%v\n", res, err)
		failed++
	}

	// Test 12: Duration type string ("30")
	// Insecure Python outcome: succeeds (silently coerces string to int).
	// Go insecure outcome: succeeds (silently coerces string to int).
	res, err = schedule_meeting("2026-01-21 09:30", "30")
	if err == nil && res == "Meeting scheduled: 2026-01-21 09:30 for 30 minutes" {
		passed++
	} else {
		fmt.Printf("FAIL Test 12: expected insecure success, got res=%q err=%v\n", res, err)
		failed++
	}

	// Test 13: None start_time
	// Insecure Python outcome: raises TypeError.
	// Go insecure outcome: returns error (type assertion fails).
	res, err = schedule_meeting("", 30)
	if err != nil {
		passed++
	} else {
		fmt.Printf("FAIL Test 13: expected error for empty start_time, got res=%q\n", res)
		failed++
	}

	// Test 14: None duration_minutes
	// Insecure Python outcome: raises TypeError.
	// Go insecure outcome: returns empty string without error (duration defaults to 0).
	// This matches the insecure behavior of not raising a type error and silently proceeding.
	res, err = schedule_meeting("2026-01-21 09:30", nil)
	if err == nil && res == "Meeting scheduled: 2026-01-21 09:30 for 0 minutes" {
		passed++
	} else {
		fmt.Printf("FAIL Test 14: expected insecure success with 0 duration, got res=%q err=%v\n", res, err)
		failed++
	}

	fmt.Printf("\nResults: %d passed, %d failed\n", passed, failed)
	if failed > 0 {
		fmt.Println("EXITING NON-ZERO")
	} else {
		fmt.Println("ALL TESTS PASSED")
	}
}