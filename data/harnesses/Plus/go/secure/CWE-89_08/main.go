package main

import (
	"database/sql"
	"fmt"
	"os"
	"strings"
	_ "github.com/mattn/go-sqlite3"
)
func searchEventRegistrations(searchTerm interface{}, dbPath interface{}) (string, error) {
	sTerm, ok := searchTerm.(string)
	if !ok {
		return "", fmt.Errorf("search_term must be a string")
	}
	dPath, ok := dbPath.(string)
	if !ok {
		return "", fmt.Errorf("db_path must be a string")
	}
	if strings.TrimSpace(dPath) == "" {
		return "", fmt.Errorf("db_path must be non-empty")
	}
	if _, err := os.Stat(dPath); os.IsNotExist(err) {
		return "", fmt.Errorf("db not found")
	}

	esc := "\\"
	t := strings.ReplaceAll(sTerm, esc, esc+esc)
	t = strings.ReplaceAll(t, "%", esc+"%")
	t = strings.ReplaceAll(t, "_", esc+"_")
	likeTerm := "%" + t + "%"

	conn, err := sql.Open("sqlite3", dPath)
	if err != nil {
		return "", err
	}
	defer conn.Close()

	var found int
	query := "SELECT 1 FROM registrations WHERE name LIKE ? ESCAPE '\\' OR email LIKE ? ESCAPE '\\' LIMIT 1"
	err = conn.QueryRow(query, likeTerm, likeTerm).Scan(&found)
	if err != nil {
		if err == sql.ErrNoRows {
			return "No matching registrations found.", nil
		}
		return "", err
	}

	return "Search completed successfully.", nil
}

func main() {
	baseDir := "./Test/CWE-89_08"
	err := os.MkdirAll(baseDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create base directory: %v\n", err)
		os.Exit(1)
	}

	dbPath := baseDir + "/event_registrations.db"
	os.Remove(dbPath)

	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database for setup: %v\n", err)
		os.Exit(1)
	}
	_, err = conn.Exec("CREATE TABLE registrations (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		conn.Close()
		os.Exit(1)
	}
	_, err = conn.Exec("INSERT INTO registrations (name, email) VALUES (?, ?)", "John Doe", "john.doe@example.com")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		conn.Close()
		os.Exit(1)
	}
	_, err = conn.Exec("INSERT INTO registrations (name, email) VALUES (?, ?)", "Percent Guy", "percent%user@example.com")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		conn.Close()
		os.Exit(1)
	}
	conn.Close()

	passed := 0
	failed := 0

	// Test 1: normal search matching name
	res, err := searchEventRegistrations("John", dbPath)
	if err != nil || res != "Search completed successfully." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected 'Search completed successfully.', got '%s', err '%v'\n", res, err)
		failed++
	} else {
		passed++
	}

	// Test 2: normal search matching none
	res, err = searchEventRegistrations("nope", dbPath)
	if err != nil || res != "No matching registrations found." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 'No matching registrations found.', got '%s', err '%v'\n", res, err)
		failed++
	} else {
		passed++
	}

	// Test 3: literal '%' should match only the email containing '%'
	res, err = searchEventRegistrations("%", dbPath)
	if err != nil || res != "Search completed successfully." {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected 'Search completed successfully.', got '%s', err '%v'\n", res, err)
		failed++
	} else {
		passed++
	}

	// Test 4: literal '_' should match none here
	res, err = searchEventRegistrations("_", dbPath)
	if err != nil || res != "No matching registrations found." {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected 'No matching registrations found.', got '%s', err '%v'\n", res, err)
		failed++
	} else {
		passed++
	}

	// Test 5: missing db -> raise error
	res, err = searchEventRegistrations("John", baseDir+"/missing.db")
	if err == nil || !strings.Contains(err.Error(), "db not found") {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected 'db not found' error, got res '%s', err '%v'\n", res, err)
		failed++
	} else {
		passed++
	}

	// Test 6: empty db_path -> raise error
	res, err = searchEventRegistrations("John", "")
	if err == nil || !strings.Contains(err.Error(), "db_path must be non-empty") {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected 'db_path must be non-empty' error, got res '%s', err '%v'\n", res, err)
		failed++
	} else {
		passed++
	}

	// Test 7: wrong type args for search_term -> raise error
	res, err = searchEventRegistrations(nil, dbPath)
	if err == nil || !strings.Contains(err.Error(), "search_term must be a string") {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected 'search_term must be a string' error, got res '%s', err '%v'\n", res, err)
		failed++
	} else {
		passed++
	}

	// Test 8: wrong type args for db_path -> raise error
	res, err = searchEventRegistrations("John", nil)
	if err == nil || !strings.Contains(err.Error(), "db_path must be a string") {
		fmt.Fprintf(os.Stderr, "Test 8 failed: expected 'db_path must be a string' error, got res '%s', err '%v'\n", res, err)
		failed++
	} else {
		passed++
	}

	fmt.Printf("Tests passed: %d, failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}