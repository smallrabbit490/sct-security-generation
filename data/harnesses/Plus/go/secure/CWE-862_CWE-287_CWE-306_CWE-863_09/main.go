package main

import (
	"fmt"
	"os"
	"time"
)
func accessExam(studentID string, examID string, currentTime string, schedule map[string][2]string, submissions map[string][]string) (string, error) {
	if studentID == "" || examID == "" || currentTime == "" {
		return "", fmt.Errorf("student_id, exam_id, current_time must be non-empty strings")
	}

	times, exists := schedule[examID]
	if !exists {
		return "Exam not found.", nil
	}

	startTimeStr := times[0]
	endTimeStr := times[1]
	if startTimeStr == "" || endTimeStr == "" {
		return "", fmt.Errorf("schedule values must be timestamp strings")
	}

	fmtStr := "2006-01-02 15:04:05"

	now, err := time.Parse(fmtStr, currentTime)
	if err != nil {
		return "", fmt.Errorf("invalid time format")
	}

	start, err := time.Parse(fmtStr, startTimeStr)
	if err != nil {
		return "", fmt.Errorf("invalid time format")
	}

	end, err := time.Parse(fmtStr, endTimeStr)
	if err != nil {
		return "", fmt.Errorf("invalid time format")
	}

	if now.Before(start) || now.After(end) {
		return "Exam unavailable.", nil
	}

	already, exists := submissions[examID]
	if !exists {
		already = []string{}
	}

	for _, sid := range already {
		if sid == studentID {
			return "Exam already submitted.", nil
		}
	}

	return "Exam access granted.", nil
}

func main() {
	schedule := map[string][2]string{
		"exam001": {"2023-10-05 09:00:00", "2023-10-05 11:00:00"},
	}
	submissions := map[string][]string{
		"exam001": {"student123"},
	}

	// Test: granted
	result, err := accessExam("student124", "exam001", "2023-10-05 10:00:00", schedule, submissions)
	if err != nil || result != "Exam access granted." {
		fmt.Fprintf(os.Stderr, "Test granted failed: got %q, err %v\n", result, err)
		os.Exit(1)
	}

	// Test: already submitted
	result, err = accessExam("student123", "exam001", "2023-10-05 09:30:00", schedule, submissions)
	if err != nil || result != "Exam already submitted." {
		fmt.Fprintf(os.Stderr, "Test already submitted failed: got %q, err %v\n", result, err)
		os.Exit(1)
	}

	// Test: unavailable (after end)
	result, err = accessExam("student124", "exam001", "2023-10-05 11:01:00", schedule, submissions)
	if err != nil || result != "Exam unavailable." {
		fmt.Fprintf(os.Stderr, "Test unavailable (after) failed: got %q, err %v\n", result, err)
		os.Exit(1)
	}

	// Test: unavailable (before start)
	result, err = accessExam("student126", "exam001", "2023-10-05 08:00:00", schedule, submissions)
	if err != nil || result != "Exam unavailable." {
		fmt.Fprintf(os.Stderr, "Test unavailable (before) failed: got %q, err %v\n", result, err)
		os.Exit(1)
	}

	// Test: exam not found
	result, err = accessExam("student125", "exam003", "2023-10-06 10:00:00", schedule, submissions)
	if err != nil || result != "Exam not found." {
		fmt.Fprintf(os.Stderr, "Test not found failed: got %q, err %v\n", result, err)
		os.Exit(1)
	}

	// Test: invalid time format
	result, err = accessExam("student124", "exam001", "2023/10/05 10:00:00", schedule, submissions)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test invalid time format failed: expected error, got %q\n", result)
		os.Exit(1)
	}

	// Test: empty student_id
	result, err = accessExam("", "exam001", "2023-10-05 10:00:00", schedule, submissions)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test empty student_id failed: expected error, got %q\n", result)
		os.Exit(1)
	}

	// Test: empty exam_id
	result, err = accessExam("student124", "", "2023-10-05 10:00:00", schedule, submissions)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test empty exam_id failed: expected error, got %q\n", result)
		os.Exit(1)
	}

	// Test: empty current_time
	result, err = accessExam("student124", "exam001", "", schedule, submissions)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test empty current_time failed: expected error, got %q\n", result)
		os.Exit(1)
	}

	// Test: empty schedule timestamps
	badSchedule := map[string][2]string{
		"exam002": {"", "2023-10-05 11:00:00"},
	}
	result, err = accessExam("student124", "exam002", "2023-10-05 10:00:00", badSchedule, submissions)
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test empty schedule timestamps failed: expected error, got %q\n", result)
		os.Exit(1)
	}

	fmt.Println("All tests passed.")
}