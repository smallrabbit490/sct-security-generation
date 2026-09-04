package main

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	_ "github.com/mattn/go-sqlite3"
)
// searchEventRegistrations is the translated insecure function.
// Insecure behavior: It uses fmt.Sprintf to directly interpolate the search term
// into the SQL LIKE clause without escaping. This means that SQL wildcards
// like '%' and '_' in the search term are treated as wildcards by the SQL engine,
// rather than as literal characters. A secure implementation would escape these
// characters or use parameterized queries with an ESCAPE clause.
func searchEventRegistrations(searchTerm string, dbPath string) string {
	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		panic(err)
	}
	defer conn.Close()

	query := fmt.Sprintf("SELECT * FROM registrations WHERE name LIKE '%%%s%%' OR email LIKE '%%%s%%'", searchTerm, searchTerm)

	rows, err := conn.Query(query)
	if err != nil {
		panic(err)
	}
	defer rows.Close()

	hasResults := false
	for rows.Next() {
		hasResults = true
		columns, _ := rows.Columns()
		vals := make([]interface{}, len(columns))
		rows.Scan(vals...)
	}

	if hasResults {
		return "Search completed successfully."
	}
	return "No matching registrations found."
}

func main() {
	// --- Inferred Python Insecure Outcome ---
	// The original Python code uses f-strings to format the search term directly into the SQL query.
	// This fails to escape SQL wildcards ('%' and '_'). When the search term is "%", the SQL
	// engine evaluates `LIKE '%%%'`, which matches ANY string. Thus, the insecure Python code
	// returns "Search completed successfully." for search_term="%", even though a literal
	// substring match for "%" should only match the row containing "percent%user@example.com".
	// Wait, actually `LIKE '%%%'` matches any string, so it DOES return "Search completed successfully."
	// which happens to be the same result as matching the literal '%'. However, for search_term="_",
	// the SQL evaluates `LIKE '%_%'`, which matches ANY non-empty string. The insecure Python code
	// returns "Search completed successfully." for "_", whereas a secure literal substring match
	// would return "No matching registrations found.".
	//
	// --- Target-Language Outcome Being Compared ---
	// We test the Go translation with search_term="_". If the translation is insecure (matching
	// the Python behavior), it will return "Search completed successfully." because the SQL
	// wildcard '_' matches any single character. If the translation is secure (escapes wildcards),
	// it will return "No matching registrations found.".
	// The validation succeeds (exits 0) only if the Go code produces the insecure outcome.

	baseDir := filepath.Join(".", "Test", "CWE-89_08")
	os.MkdirAll(baseDir, 0755)

	dbPath := filepath.Join(baseDir, "event_registrations.db")
	os.Remove(dbPath)

	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(2)
	}
	_, err = conn.Exec("CREATE TABLE registrations (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(2)
	}
	_, err = conn.Exec("INSERT INTO registrations (name, email) VALUES (?, ?)", "John Doe", "john.doe@example.com")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(2)
	}
	_, err = conn.Exec("INSERT INTO registrations (name, email) VALUES (?, ?)", "Percent Guy", "percent%user@example.com")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(2)
	}
	conn.Close()

	// Test with search_term="_"
	// Insecure outcome: "Search completed successfully." (because '_' acts as a wildcard matching any character)
	// Secure outcome: "No matching registrations found." (because '_' is treated as a literal character)
	result := searchEventRegistrations("_", dbPath)

	if result == "Search completed successfully." {
		// Matches the insecure Python behavior
		fmt.Println("Validation passed: Insecure behavior confirmed.")
		os.Exit(0)
	} else {
		// The vulnerability was fixed or behavior differs from the expected insecure outcome
		fmt.Fprintf(os.Stderr, "Validation failed: Expected insecure outcome 'Search completed successfully.', got '%s'\n", result)
		os.Exit(1)
	}
}