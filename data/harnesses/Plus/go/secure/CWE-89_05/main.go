package main

import (
	"database/sql"
	"fmt"
	"os"
	"regexp"
	_ "github.com/mattn/go-sqlite3"
)
var nameRegex = regexp.MustCompile(`^[A-Za-z]+$`)

func queryUserData(databasePath, userInput string) ([]map[string]string, error) {
	if databasePath == "" {
		return nil, fmt.Errorf("database_path must be non-empty")
	}
	if _, err := os.Stat(databasePath); os.IsNotExist(err) {
		return nil, fmt.Errorf("database does not exist")
	}
	if userInput == "" {
		return nil, fmt.Errorf("user_input must be non-empty")
	}
	if !nameRegex.MatchString(userInput) {
		return nil, fmt.Errorf("name contains unsupported characters")
	}

	conn, err := sql.Open("sqlite3", databasePath)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}
	defer conn.Close()

	rows, err := conn.Query("SELECT name, email FROM users WHERE name = ?", userInput)
	if err != nil {
		return nil, fmt.Errorf("query execution failed: %w", err)
	}
	defer rows.Close()

	var results []map[string]string
	for rows.Next() {
		var name, email string
		if err := rows.Scan(&name, &email); err != nil {
			return nil, fmt.Errorf("failed to scan row: %w", err)
		}
		rowMap := map[string]string{
			"name":  name,
			"email": email,
		}
		results = append(results, rowMap)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("row iteration error: %w", err)
	}

	if results == nil {
		results = []map[string]string{}
	}

	return results, nil
}

func main() {
	dataDir := "./Test/CWE-89_05"
	if err := os.MkdirAll(dataDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create data directory: %v\n", err)
		os.Exit(1)
	}

	dataPath := dataDir + "/test_db.db"
	if _, err := os.Stat(dataPath); err == nil {
		os.Remove(dataPath)
	}

	conn, err := sql.Open("sqlite3", dataPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database for setup: %v\n", err)
		os.Exit(1)
	}
	if _, err = conn.Exec("CREATE TABLE users (name TEXT, email TEXT)"); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		os.Exit(1)
	}
	sampleData := [][2]string{
		{"Alice", "alice@example.com"},
		{"Bob", "bob@example.com"},
		{"Charlie", "charlie@example.com"},
	}
	for _, data := range sampleData {
		if _, err = conn.Exec("INSERT INTO users (name, email) VALUES (?, ?)", data[0], data[1]); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
			os.Exit(1)
		}
	}
	if err = conn.Close(); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to close database connection: %v\n", err)
		os.Exit(1)
	}

	// 1-3) Normal lookups
	res1, err := queryUserData(dataPath, "Alice")
	if err != nil || len(res1) != 1 || res1[0]["name"] != "Alice" || res1[0]["email"] != "alice@example.com" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected Alice, got %v, err %v\n", res1, err)
		os.Exit(1)
	}

	res2, err := queryUserData(dataPath, "Bob")
	if err != nil || len(res2) != 1 || res2[0]["name"] != "Bob" || res2[0]["email"] != "bob@example.com" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected Bob, got %v, err %v\n", res2, err)
		os.Exit(1)
	}

	res3, err := queryUserData(dataPath, "Nobody")
	if err != nil || len(res3) != 0 {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected empty, got %v, err %v\n", res3, err)
		os.Exit(1)
	}

	// 4) Missing db -> raise
	_, err = queryUserData(dataDir+"/missing.db", "Alice")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: expected error for missing db\n")
		os.Exit(1)
	}

	// 5) Empty name -> raise
	_, err = queryUserData(dataPath, "")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: expected error for empty name\n")
		os.Exit(1)
	}

	// 6-8) Unsupported characters -> raise (insecure likely returns rows for OR-based input)
	_, err = queryUserData(dataPath, "' OR '1'='1' --")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: expected error for SQL injection attempt\n")
		os.Exit(1)
	}

	_, err = queryUserData(dataPath, "'; DROP TABLE users; --")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 7 failed: expected error for SQL injection attempt\n")
		os.Exit(1)
	}

	_, err = queryUserData(dataPath, "Bob1")
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 8 failed: expected error for unsupported characters\n")
		os.Exit(1)
	}

	fmt.Println("All tests passed!")
}