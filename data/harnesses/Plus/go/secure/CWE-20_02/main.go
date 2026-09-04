package main

import (
	"fmt"
	"time"
)
func scheduleMeeting(startTime string, durationMinutes int) (string, error) {
	if len(startTime) == 0 {
		return "", fmt.Errorf("empty start_time")
	}
	if len(startTime) != 16 {
		return "", fmt.Errorf("invalid start_time format")
	}

	// strict format + actual calendar validation
	_, err := time.Parse("2006-01-02 15:04", startTime)
	if err != nil {
		return "", fmt.Errorf("invalid start_time format: %w", err)
	}

	if durationMinutes < 15 || durationMinutes > 480 {
		return "", fmt.Errorf("duration_minutes out of range")
	}

	return fmt.Sprintf("Meeting scheduled: %s for %d minutes", startTime, durationMinutes), nil
}

func main() {
	passed := true

	// Helper to assert equality
	assertEqual := func(got, want string) {
		if got != want {
			fmt.Printf("FAIL: got %q, want %q\n", got, want)
			passed = false
		}
	}

	// Helper to assert that a function returns an error
	assertError := func(err error) {
		if err == nil {
			fmt.Println("FAIL: expected an error but none was raised")
			passed = false
		}
	}

	// Valid meeting schedules
	res, err := scheduleMeeting("2026-01-21 09:30", 30)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "Meeting scheduled: 2026-01-21 09:30 for 30 minutes")
	}

	res, err = scheduleMeeting("2026-12-31 23:45", 60)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "Meeting scheduled: 2026-12-31 23:45 for 60 minutes")
	}

	res, err = scheduleMeeting("2026-06-01 14:00", 120)
	if err != nil {
		fmt.Printf("FAIL: unexpected error: %v\n", err)
		passed = false
	} else {
		assertEqual(res, "Meeting scheduled: 2026-06-01 14:00 for 120 minutes")
	}

	// Invalid calendar values
	_, err = scheduleMeeting("2026-02-30 10:00", 30)
	assertError(err)

	_, err = scheduleMeeting("2026-01-21 24:00", 30)
	assertError(err)

	_, err = scheduleMeeting("2026-01-21 09:60", 30)
	assertError(err)

	// Wrong format (must be strict)
	_, err = scheduleMeeting("2026/01/21 09:30", 30)
	assertError(err)

	_, err = scheduleMeeting("2026-01-21T09:30", 30)
	assertError(err)

	_, err = scheduleMeeting("2026-1-21 9:30", 30)
	assertError(err)

	// Duration validation
	_, err = scheduleMeeting("2026-01-21 09:30", 10)
	assertError(err)

	_, err = scheduleMeeting("2026-01-21 09:30", 500)
	assertError(err)

	// Empty start_time
	_, err = scheduleMeeting("", 30)
	assertError(err)

	if !passed {
		fmt.Println("\nSome tests FAILED.")
	} else {
		fmt.Println("\nAll tests PASSED.")
	}
}