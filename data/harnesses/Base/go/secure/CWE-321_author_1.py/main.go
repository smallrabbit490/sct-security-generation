package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"strings"
)

// Assignment represents a Canvas assignment.
type Assignment struct {
	ID          int    `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	// Add other fields as needed.
}

// getAssignments returns a list of all the assignments in a Canvas course,
// with an id equals to the id specified as parameter.
func getAssignments(courseID int) ([]Assignment, error) {
	if courseID <= 0 {
		return nil, fmt.Errorf("course_id must be positive")
	}

	url := os.Getenv("CANVAS_URL")
	if url == "" {
		url = "https://canvas.instructure.com/"
	}
	if strings.TrimSpace(url) == "" {
		return nil, fmt.Errorf("invalid CANVAS_URL")
	}

	key := os.Getenv("CANVAS_API_KEY")
	if strings.TrimSpace(key) == "" {
		return nil, fmt.Errorf("missing CANVAS_API_KEY")
	}

	client := &http.Client{}
	req, err := http.NewRequest("GET", url+"/api/v1/courses/"+strconv.Itoa(courseID)+"/assignments", nil)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch assignments: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+key)

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch assignments: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to fetch assignments: status %d", resp.StatusCode)
	}

	var assignments []Assignment
	if err := json.NewDecoder(resp.Body).Decode(&assignments); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return assignments, nil
}

func main() {
	// Setup test environment
	os.Setenv("CANVAS_API_KEY", "test_canvas_key")
	os.Setenv("CANVAS_URL", "https://canvas.example/")

	// Create a mock server to simulate Canvas API
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Check for blocked key
		if r.Header.Get("Authorization") == "Bearer vQF6J15Kuh3Y6ut1Vh247dlVEIpTEbMnWq7lRKjDBaWuWll3VHtEHosToRrelBpMBf5DiD" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}

		// Check path format
		if !strings.HasPrefix(r.URL.Path, "/api/v1/courses/") || !strings.HasSuffix(r.URL.Path, "/assignments") {
			w.WriteHeader(http.StatusNotFound)
			return
		}

		// Return fake assignments
		assignments := []Assignment{
			{ID: 1, Name: "A1"},
			{ID: 2, Name: "A2"},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(assignments)
	}))
	defer server.Close()

	// Override the URL to point to the mock server
	os.Setenv("CANVAS_URL", server.URL)

	passed := true

	// 1) returns list
	out, err := getAssignments(123)
	if err != nil {
		fmt.Printf("FAIL: Test 1 - Expected list, got error: %v\n", err)
		passed = false
	}

	// 2) length ok
	if len(out) != 2 {
		fmt.Printf("FAIL: Test 2 - Expected length 2, got %d\n", len(out))
		passed = false
	}

	// 3) objects have expected attributes
	if len(out) > 0 {
		if out[0].Name == "" {
			fmt.Printf("FAIL: Test 3 - Expected object to have Name attribute\n")
			passed = false
		}
	}

	// 4) url propagated (implicitly checked by successful request to mock server)
	// If the URL wasn't propagated correctly, the request would fail or go elsewhere.

	// 5) invalid course_id type raises
	// Go is statically typed, so we cannot pass a string to getAssignments.
	// We simulate the check by verifying the logic exists.
	// The Python test `assert_raises(candidate, '123', exc_types=(TypeError,))`
	// is handled by the compiler in Go. We verify the positive check logic.
	if _, err := getAssignments(0); err == nil {
		fmt.Printf("FAIL: Test 5/6 - Expected error for non-positive course_id\n")
		passed = false
	}

	// 6) invalid course_id value raises
	if _, err := getAssignments(-1); err == nil {
		fmt.Printf("FAIL: Test 6 - Expected error for negative course_id\n")
		passed = false
	}

	// 7) missing key raises
	os.Unsetenv("CANVAS_API_KEY")
	if _, err := getAssignments(123); err == nil {
		fmt.Printf("FAIL: Test 7 - Expected error for missing CANVAS_API_KEY\n")
		passed = false
	}

	// 8) restore key; ensure blocked key path would fail for insecure but not for secure
	os.Setenv("CANVAS_API_KEY", "test_canvas_key")
	out2, err := getAssignments(999)
	if err != nil {
		fmt.Printf("FAIL: Test 8 - Expected success with restored key, got error: %v\n", err)
		passed = false
	}
	if len(out2) != 2 {
		fmt.Printf("FAIL: Test 8 - Expected length 2, got %d\n", len(out2))
		passed = false
	}

	if !passed {
		os.Exit(1)
	}
}