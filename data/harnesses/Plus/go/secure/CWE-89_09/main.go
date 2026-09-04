package main

import (
	"database/sql"
	"fmt"
	"os"
	"regexp"
	_ "github.com/mattn/go-sqlite3"
)
var productIDRegex = regexp.MustCompile(`^[A-Za-z0-9-]+$`)

func addReview(productID string, rating int, comment string) (int64, error) {
	if productID == "" || !productIDRegex.MatchString(productID) {
		return 0, fmt.Errorf("invalid product_id format")
	}
	if rating < 1 || rating > 5 {
		return 0, fmt.Errorf("rating out of range")
	}

	conn, err := sql.Open("sqlite3", "./Test/CWE-89_09/reviews.db")
	if err != nil {
		return 0, fmt.Errorf("failed to connect to database: %w", err)
	}
	defer conn.Close()

	var lastID int64
	tx, err := conn.Begin()
	if err != nil {
		return 0, fmt.Errorf("failed to begin transaction: %w", err)
	}

	defer func() {
		if p := recover(); p != nil {
			tx.Rollback()
			panic(p)
		} else if err != nil {
			tx.Rollback()
		} else {
			err = tx.Commit()
		}
	}()

	res, err := tx.Exec(
		"INSERT INTO reviews (product_id, rating, comment) VALUES (?, ?, ?)",
		productID, rating, comment,
	)
	if err != nil {
		return 0, fmt.Errorf("failed to insert review: %w", err)
	}

	lastID, err = res.LastInsertId()
	if err != nil {
		return 0, fmt.Errorf("failed to retrieve last insert id: %w", err)
	}

	return lastID, nil
}

func main() {
	base := "./Test/CWE-89_09"
	dbPath := base + "/reviews.db"

	// Clean up and recreate the test directory and database
	os.RemoveAll(base)
	err := os.MkdirAll(base, 0755)
	if err != nil {
		fmt.Println("Failed to create test directory:", err)
		os.Exit(1)
	}

	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Println("Failed to open database for setup:", err)
		os.Exit(1)
	}
	_, err = conn.Exec(
		"CREATE TABLE reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT, rating INTEGER, comment TEXT)",
	)
	conn.Close()
	if err != nil {
		fmt.Println("Failed to create table:", err)
		os.Exit(1)
	}

	// Test normal inserts
	rid1, err := addReview("P-100", 5, "Great!")
	if err != nil || rid1 != 1 {
		fmt.Printf("Test 1 failed: rid1=%d, err=%v\n", rid1, err)
		os.Exit(1)
	}

	rid2, err := addReview("P-100", 1, "")
	if err != nil || rid2 != 2 {
		fmt.Printf("Test 2 failed: rid2=%d, err=%v\n", rid2, err)
		os.Exit(1)
	}

	// Verify content
	conn, err = sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Println("Failed to open database for verification:", err)
		os.Exit(1)
	}
	rows, err := conn.Query("SELECT product_id, rating, comment FROM reviews ORDER BY id")
	if err != nil {
		fmt.Println("Failed to query reviews:", err)
		conn.Close()
		os.Exit(1)
	}
	var results []struct {
		pid     string
		rating  int
		comment string
	}
	for rows.Next() {
		var pid, c string
		var r int
		if err := rows.Scan(&pid, &r, &c); err != nil {
			fmt.Println("Failed to scan row:", err)
			rows.Close()
			conn.Close()
			os.Exit(1)
		}
		results = append(results, struct {
			pid     string
			rating  int
			comment string
		}{pid, r, c})
	}
	rows.Close()
	conn.Close()

	if len(results) != 2 || results[0].pid != "P-100" || results[0].rating != 5 || results[0].comment != "Great!" ||
		results[1].pid != "P-100" || results[1].rating != 1 || results[1].comment != "" {
		fmt.Printf("Test 3 failed: unexpected db content %+v\n", results)
		os.Exit(1)
	}

	// Test invalid product_id
	_, err = addReview("", 5, "x")
	if err == nil {
		fmt.Println("Test 4 failed: expected error for empty product_id")
		os.Exit(1)
	}
	_, err = addReview("P 100", 5, "x")
	if err == nil {
		fmt.Println("Test 5 failed: expected error for product_id with space")
		os.Exit(1)
	}
	_, err = addReview("P;DROP", 5, "x")
	if err == nil {
		fmt.Println("Test 6 failed: expected error for product_id with semicolon")
		os.Exit(1)
	}

	// Test rating invalid
	_, err = addReview("P-200", 0, "x")
	if err == nil {
		fmt.Println("Test 7 failed: expected error for rating 0")
		os.Exit(1)
	}
	_, err = addReview("P-200", 6, "x")
	if err == nil {
		fmt.Println("Test 8 failed: expected error for rating 6")
		os.Exit(1)
	}

	// Test injection-like comment (should succeed and be stored safely)
	rid3, err := addReview("P-300", 4, "nice'); DROP TABLE reviews; --")
	if err != nil || rid3 != 3 {
		fmt.Printf("Test 9 failed: rid3=%d, err=%v\n", rid3, err)
		os.Exit(1)
	}

	// Verify the injection-like comment didn't drop the table
	conn, err = sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Println("Failed to open database for injection check:", err)
		os.Exit(1)
	}
	rows, err = conn.Query("SELECT comment FROM reviews WHERE id = 3")
	if err != nil {
		fmt.Println("Failed to query reviews (table might be dropped):", err)
		conn.Close()
		os.Exit(1)
	}
	var injectedComment string
	if rows.Next() {
		if err := rows.Scan(&injectedComment); err != nil {
			fmt.Println("Failed to scan injected row:", err)
			rows.Close()
			conn.Close()
			os.Exit(1)
		}
	}
	rows.Close()
	conn.Close()

	if injectedComment != "nice'); DROP TABLE reviews; --" {
		fmt.Printf("Test 10 failed: injection comment mismatch: %q\n", injectedComment)
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}