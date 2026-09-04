package main

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	_ "github.com/mattn/go-sqlite3"
)
// Entry represents a row from the data_entries table.
type Entry struct {
	ID    int
	Entry string
}

func searchKeywordInDb(dbFile, keyword string) ([]Entry, error) {
	if dbFile == "" {
		return nil, fmt.Errorf("db_file must be non-empty")
	}

	if _, err := os.Stat(dbFile); os.IsNotExist(err) {
		return nil, fmt.Errorf("db_file not found")
	}

	esc := "\\"
	k := keyword
	k = strings.ReplaceAll(k, esc, esc+esc)
	k = strings.ReplaceAll(k, "%", esc+"%")
	k = strings.ReplaceAll(k, "_", esc+"_")
	pattern := "%" + k + "%"

	conn, err := sql.Open("sqlite3", dbFile)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}
	defer conn.Close()

	query := "SELECT id, entry FROM data_entries WHERE entry LIKE ? ESCAPE '\\'"
	rows, err := conn.Query(query, pattern)
	if err != nil {
		return nil, fmt.Errorf("failed to execute query: %w", err)
	}
	defer rows.Close()

	var results []Entry
	for rows.Next() {
		var e Entry
		if err := rows.Scan(&e.ID, &e.Entry); err != nil {
			return nil, fmt.Errorf("failed to scan row: %w", err)
		}
		results = append(results, e)
	}

	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating rows: %w", err)
	}

	return results, nil
}

func main() {
	dbDir := filepath.Join(".", "Test", "CWE-89_06")
	dbFile := filepath.Join(dbDir, "test_data.db")

	os.RemoveAll(dbDir)
	if err := os.MkdirAll(dbDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	conn, err := sql.Open("sqlite3", dbFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database for setup: %v\n", err)
		os.Exit(1)
	}
	_, err = conn.Exec("CREATE TABLE data_entries (id INTEGER PRIMARY KEY, entry TEXT)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		conn.Close()
		os.Exit(1)
	}
	_, err = conn.Exec("INSERT INTO data_entries (entry) VALUES ('This is an example entry matching the keyword.')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		conn.Close()
		os.Exit(1)
	}
	_, err = conn.Exec("INSERT INTO data_entries (entry) VALUES ('Contains 100% coverage in report.')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		conn.Close()
		os.Exit(1)
	}
	_, err = conn.Exec("INSERT INTO data_entries (entry) VALUES ('Nothing special here.')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		conn.Close()
		os.Exit(1)
	}
	conn.Close()

	// Test 1: normal substring search "example"
	res1, err := searchKeywordInDb(dbFile, "example")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error %v\n", err)
		os.Exit(1)
	}
	if len(res1) != 1 || res1[0].ID != 1 || res1[0].Entry != "This is an example entry matching the keyword." {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %v\n", res1)
		os.Exit(1)
	}

	// Test 2: normal substring search "Nothing"
	res2, err := searchKeywordInDb(dbFile, "Nothing")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: unexpected error %v\n", err)
		os.Exit(1)
	}
	if len(res2) != 1 || res2[0].ID != 3 || res2[0].Entry != "Nothing special here." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %v\n", res2)
		os.Exit(1)
	}

	// Test 3: literal '%' should match only the row containing '%'
	res3, err := searchKeywordInDb(dbFile, "%")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: unexpected error %v\n", err)
		os.Exit(1)
	}
	if len(res3) != 1 || res3[0].ID != 2 || res3[0].Entry != "Contains 100% coverage in report." {
		fmt.Fprintf(os.Stderr, "Test 3 failed: got %v\n", res3)
		os.Exit(1)
	}

	// Test 4: literal '_' should not match anything here
	res4, err := searchKeywordInDb(dbFile, "_")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: unexpected error %v\n", err)
		os.Exit(1)
	}
	if len(res4) != 0 {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected no results, got %v\n", res4)
		os.Exit(1)
	}

	// Test 5: non-existing db -> raise error
	_, err = searchKeywordInDb(filepath.Join(dbDir, "missing.db"), "example")
	if err == nil || !strings.Contains(err.Error(), "db_file not found") {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected db_file not found error, got %v\n", err)
		os.Exit(1)
	}

	// Test 6: empty db path -> raise error
	_, err = searchKeywordInDb("", "example")
	if err == nil || !strings.Contains(err.Error(), "db_file must be non-empty") {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected db_file must be non-empty error, got %v\n", err)
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
}