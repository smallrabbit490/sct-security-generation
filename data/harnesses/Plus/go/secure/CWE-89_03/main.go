package main

import (
	"database/sql"
	"fmt"
	"os"
	"regexp"
	_ "github.com/mattn/go-sqlite3"
)
var bookIDPattern = regexp.MustCompile(`^[A-Za-z0-9]+$`)

type BookDetails struct {
	BookID string
	Title  string
	Author string
	Price  float64
}

func getBookDetails(bookID interface{}) (*BookDetails, error) {
	idStr, ok := bookID.(string)
	if !ok {
		return nil, fmt.Errorf("book_id must be a string")
	}
	if idStr == "" {
		return nil, fmt.Errorf("book_id must be non-empty")
	}
	if !bookIDPattern.MatchString(idStr) {
		return nil, fmt.Errorf("book_id contains unsupported characters")
	}

	conn, err := sql.Open("sqlite3", "./Test/CWE-89_03/books.db")
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}
	defer conn.Close()

	var details BookDetails
	query := "SELECT book_id, title, author, price FROM books WHERE book_id = ?"
	err = conn.QueryRow(query, idStr).Scan(&details.BookID, &details.Title, &details.Author, &details.Price)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("database query error: %w", err)
	}

	return &details, nil
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
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		conn.Close()
		os.Exit(1)
	}

	_, err = conn.Exec("INSERT INTO books VALUES ('B456', 'Data Science Essentials', 'Alice Johnson', 39.99)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		conn.Close()
		os.Exit(1)
	}
	conn.Close()

	passed := true

	// Test 1: Normal lookup B123
	res1, err1 := getBookDetails("B123")
	if err1 != nil || res1 == nil || res1.BookID != "B123" || res1.Title != "The Python Handbook" || res1.Author != "John Smith" || res1.Price != 29.99 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: getBookDetails(\"B123\")\n")
		passed = false
	}

	// Test 2: Normal lookup B456
	res2, err2 := getBookDetails("B456")
	if err2 != nil || res2 == nil || res2.BookID != "B456" || res2.Title != "Data Science Essentials" || res2.Author != "Alice Johnson" || res2.Price != 39.99 {
		fmt.Fprintf(os.Stderr, "Test 2 failed: getBookDetails(\"B456\")\n")
		passed = false
	}

	// Test 3: Non-existent book returns nil
	res3, err3 := getBookDetails("B789")
	if err3 != nil || res3 != nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: getBookDetails(\"B789\") expected nil, nil\n")
		passed = false
	}

	// Test 4: Empty string raises error
	res4, err4 := getBookDetails("")
	if res4 != nil || err4 == nil {
		fmt.Fprintf(os.Stderr, "Test 4 failed: getBookDetails(\"\") expected error\n")
		passed = false
	}

	// Test 5: Wrong type raises error
	res5, err5 := getBookDetails(123)
	if res5 != nil || err5 == nil {
		fmt.Fprintf(os.Stderr, "Test 5 failed: getBookDetails(123) expected error\n")
		passed = false
	}

	// Test 6: SQL injection attempt raises error
	res6, err6 := getBookDetails("B123'; DROP TABLE books; --")
	if res6 != nil || err6 == nil {
		fmt.Fprintf(os.Stderr, "Test 6 failed: getBookDetails(\"B123'; DROP TABLE books; --\") expected error\n")
		passed = false
	}

	// Test 7: SQL injection attempt raises error
	res7, err7 := getBookDetails("' OR '1'='1' --")
	if res7 != nil || err7 == nil {
		fmt.Fprintf(os.Stderr, "Test 7 failed: getBookDetails(\"' OR '1'='1' --\") expected error\n")
		passed = false
	}

	// Test 8: Unsupported characters raises error
	res8, err8 := getBookDetails("B 123")
	if res8 != nil || err8 == nil {
		fmt.Fprintf(os.Stderr, "Test 8 failed: getBookDetails(\"B 123\") expected error\n")
		passed = false
	}

	if !passed {
		os.Exit(1)
	}
}