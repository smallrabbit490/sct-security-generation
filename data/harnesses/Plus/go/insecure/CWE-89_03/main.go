package main

import (
	"database/sql"
	"fmt"
	"os"
	_ "github.com/mattn/go-sqlite3"
)
// getBookDetails retrieves a row from the books table for the given book ID.
// Inferred Python insecure outcome: The Python code uses f-string formatting to build
// the SQL query, making it vulnerable to SQL injection. It does not validate the
// book_id input, so malicious inputs like "B123'; DROP TABLE books; --" are
// concatenated directly into the query instead of raising a ValueError.
// Target-language outcome: The Go translation also uses fmt.Sprintf to build the
// query without validating the book_id, exposing the same SQL injection vulnerability.
func getBookDetails(bookID string) interface{} {
	conn, err := sql.Open("sqlite3", "./Test/CWE-89_03/books.db")
	if err != nil {
		panic(err)
	}
	defer conn.Close()

	query := fmt.Sprintf("SELECT * FROM books WHERE book_id = '%s'", bookID)

	row := conn.QueryRow(query)

	var bID string
	var title string
	var author string
	var price float64

	err = row.Scan(&bID, &title, &author, &price)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil
		}
		panic(err)
	}

	return []interface{}{bID, title, author, price}
}

func main() {
	testDir := "./Test/CWE-89_03"
	err := os.MkdirAll(testDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	dbPath := testDir + "/books.db"
	os.Remove(dbPath)

	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database for setup: %v\n", err)
		os.Exit(1)
	}

	_, err = conn.Exec("CREATE TABLE books (book_id TEXT PRIMARY KEY, title TEXT, author TEXT, price REAL)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		conn.Close()
		os.Exit(1)
	}

	_, err = conn.Exec("INSERT INTO books VALUES ('B123', 'The Python Handbook', 'John Smith', 29.99)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert B123: %v\n", err)
		conn.Close()
		os.Exit(1)
	}

	_, err = conn.Exec("INSERT INTO books VALUES ('B456', 'Data Science Essentials', 'Alice Johnson', 39.99)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert B456: %v\n", err)
		conn.Close()
		os.Exit(1)
	}

	conn.Close()

	// Test 1-3: Normal lookups
	res1 := getBookDetails("B123")
	arr1, ok := res1.([]interface{})
	if !ok || arr1[0].(string) != "B123" || arr1[1].(string) != "The Python Handbook" || arr1[2].(string) != "John Smith" || arr1[3].(float64) != 29.99 {
		fmt.Fprintln(os.Stderr, "Test 1 failed: B123 lookup incorrect")
		os.Exit(1)
	}

	res2 := getBookDetails("B456")
	arr2, ok := res2.([]interface{})
	if !ok || arr2[0].(string) != "B456" || arr2[1].(string) != "Data Science Essentials" || arr2[2].(string) != "Alice Johnson" || arr2[3].(float64) != 39.99 {
		fmt.Fprintln(os.Stderr, "Test 2 failed: B456 lookup incorrect")
		os.Exit(1)
	}

	res3 := getBookDetails("B789")
	if res3 != nil {
		fmt.Fprintln(os.Stderr, "Test 3 failed: B789 should be nil")
		os.Exit(1)
	}

	// Test 6-8: SQL Injection / unsupported characters
	// The Python insecure code does NOT validate inputs and raises no ValueError for these.
	// It simply passes the malicious string directly into the SQL query.
	// The Go translation must match this insecure behavior (no panic/exception for these inputs).
	injectionInputs := []string{
		"B123'; DROP TABLE books; --",
		"' OR '1'='1' --",
		"B 123",
	}

	for _, input := range injectionInputs {
		func() {
			defer func() {
				if r := recover(); r != nil {
					// If the Go code panics (raises an exception) for these inputs, it is
					// securely failing, which does NOT match the insecure Python behavior.
					fmt.Fprintf(os.Stderr, "Test failed: input %q caused a panic, but insecure Python code would not raise ValueError\n", input)
					os.Exit(1)
				}
			}()

			// Call the function with the injection input
			_ = getBookDetails(input)
		}()
	}

	// Verify that the SQL injection actually affected the database (leaked data or dropped table)
	// to confirm the vulnerability exists and is not just a benign string.
	conn, err = sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to reopen database for injection check: %v\n", err)
		os.Exit(1)
	}

	var tableName string
	err = conn.QueryRow("SELECT name FROM sqlite_master WHERE type='table' AND name='books'").Scan(&tableName)
	conn.Close()

	if tableName != "books" {
		// The table was dropped by the SQL injection, confirming the vulnerability executed.
		fmt.Fprintln(os.Stderr, "SQL injection successfully dropped the table (insecure behavior confirmed)")
		os.Exit(0)
	}

	// If the table wasn't dropped, check if the "' OR '1'='1' --" injection leaked data
	// by checking if it returned a row instead of nil.
	leakResult := getBookDetails("' OR '1'='1' --")
	if leakResult != nil {
		// The injection leaked data, confirming the vulnerability.
		fmt.Fprintln(os.Stderr, "SQL injection successfully leaked data (insecure behavior confirmed)")
		os.Exit(0)
	}

	// If the code reaches here, it means the inputs didn't panic (matching Python's lack of ValueError),
	// but we also couldn't confirm the SQL injection had any effect.
	// We check if the input was safely parameterized (which would mean the vulnerability is fixed).
	// Since the code uses fmt.Sprintf, it's definitely vulnerable, but the SQLite driver might have
	// rejected the multi-statement drop. The leak check above should catch the OR injection.
	// If neither dropped the table nor leaked data, but no panic occurred, it matches the Python
	// insecure behavior of not raising an exception for bad characters.
	fmt.Fprintln(os.Stderr, "No panic on injection inputs (matches insecure Python behavior)")
	os.Exit(0)
}