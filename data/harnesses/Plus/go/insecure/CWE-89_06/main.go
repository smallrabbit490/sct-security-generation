package main

import (
	"database/sql"
	"fmt"
	"os"
	"strings"
	_ "github.com/mattn/go-sqlite3"
)
// searchKeywordInDb is the translated insecure function.
// Inferred Python insecure outcome: The Python code uses an f-string to format the keyword
// directly into the SQL query, making it vulnerable to SQL injection (CWE-89).
// For example, a keyword like "' OR 1=1 --" would modify the query to return all rows.
// The Go translation uses fmt.Sprintf similarly, embedding the keyword directly into the query string.
// Target-language outcome being compared: The Go code must exhibit the same SQL injection vulnerability,
// returning all rows when injected, rather than safely parameterizing the query.
func searchKeywordInDb(dbFile string, keyword string) []struct {
	Id    int
	Entry string
} {
	conn, err := sql.Open("sqlite3", dbFile)
	if err != nil {
		panic(err)
	}
	defer conn.Close()

	query := fmt.Sprintf("SELECT * FROM data_entries WHERE entry LIKE '%%%s%%' ESCAPE '\\'", keyword)

	rows, err := conn.Query(query)
	if err != nil {
		panic(err)
	}
	defer rows.Close()

	var results []struct {
		Id    int
		Entry string
	}

	for rows.Next() {
		var id int
		var entry string
		if err := rows.Scan(&id, &entry); err != nil {
			panic(err)
		}
		results = append(results, struct {
			Id    int
			Entry string
		}{id, entry})
	}

	if err := rows.Err(); err != nil {
		panic(err)
	}

	return results
}

func main() {
	dbDir := "./Test/CWE-89_06"
	dbFile := dbDir + "/test_data.db"

	os.RemoveAll(dbDir)
	err := os.MkdirAll(dbDir, 0755)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	conn, err := sql.Open("sqlite3", dbFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to open database: %v\n", err)
		os.Exit(1)
	}
	_, err = conn.Exec("CREATE TABLE data_entries (id INTEGER PRIMARY KEY, entry TEXT)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create table: %v\n", err)
		os.Exit(1)
	}
	_, err = conn.Exec("INSERT INTO data_entries (entry) VALUES ('This is an example entry matching the keyword.')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		os.Exit(1)
	}
	_, err = conn.Exec("INSERT INTO data_entries (entry) VALUES ('Contains 100% coverage in report.')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		os.Exit(1)
	}
	_, err = conn.Exec("INSERT INTO data_entries (entry) VALUES ('Nothing special here.')")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to insert data: %v\n", err)
		os.Exit(1)
	}
	conn.Close()

	// Test 1: SQL Injection vulnerability check
	// The insecure Python code formats the keyword directly into the SQL string.
	// If the keyword is "' OR 1=1 --", the query becomes:
	// SELECT * FROM data_entries WHERE entry LIKE '%%' OR 1=1 --%' ESCAPE '\'
	// This should return all 3 rows if the vulnerability is present.
	injectKeyword := "' OR 1=1 --"
	results := searchKeywordInDb(dbFile, injectKeyword)
	if len(results) != 3 {
		fmt.Fprintf(os.Stderr, "Test 1 failed: insecure code should be vulnerable to SQL injection and return 3 rows, got %d\n", len(results))
		os.Exit(1)
	}

	// Test 2: Normal substring search
	results = searchKeywordInDb(dbFile, "example")
	if len(results) != 1 || results[0].Entry != "This is an example entry matching the keyword." {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected 1 result for 'example', got %d\n", len(results))
		os.Exit(1)
	}

	// Test 3: Literal '%' search
	// The insecure code uses ESCAPE '\' but does not escape the keyword itself.
	// If the keyword is "%", the query becomes LIKE '%%%' ESCAPE '\', which matches
	// any string containing '%' as well as any string (due to unescaped wildcards).
	// A secure parameterized query would only match the literal '%'.
	results = searchKeywordInDb(dbFile, "%")
	hasLiteralPercent := false
	for _, r := range results {
		if strings.Contains(r.Entry, "%") {
			hasLiteralPercent = true
		}
	}
	// If the code were secure, it would ONLY return the row with '%'.
	// Because it's insecure and doesn't escape the '%' in the keyword, it matches
	// everything (or at least more than just the literal '%'), so it returns > 1 row
	// or at least matches strings without '%'.
	if !hasLiteralPercent || len(results) < 2 {
		fmt.Fprintf(os.Stderr, "Test 3 failed: insecure code should fail to escape literal '%%' properly, got %d results\n", len(results))
		os.Exit(1)
	}

	fmt.Println("All validation checks passed (insecure behavior confirmed).")
}