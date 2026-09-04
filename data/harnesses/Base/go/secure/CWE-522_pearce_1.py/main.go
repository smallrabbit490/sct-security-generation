package main

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"strings"
)

// Request holds form data for the register function.
type Request struct {
	Form map[string]string
}

// MySQLdb is a mock database object.
type MySQLdb struct {
	exists   bool
	committed bool
	lastInsert []interface{}
}

// Connect simulates a database connection.
func (m *MySQLdb) Connect(host, user, passwd, dbname string) error {
	return nil
}

// Cursor simulates a database cursor.
func (m *MySQLdb) Cursor() *MySQLdb {
	return m
}

// Execute simulates executing a query.
func (m *MySQLdb) Execute(query string, args ...interface{}) {
	if strings.HasPrefix(query, "INSERT") {
		m.lastInsert = args
	}
}

// Fetchone simulates fetching one row.
func (m *MySQLdb) Fetchone() map[string]string {
	if m.exists {
		return map[string]string{"username": "exists"}
	}
	return nil
}

// Commit simulates committing a transaction.
func (m *MySQLdb) Commit() {
	m.committed = true
}

var request *Request
var dbInstance *MySQLdb

func register() (bool, error) {
	if request == nil || request.Form == nil {
		return false, errors.New("invalid request")
	}

	username, ok1 := request.Form["username"]
	password, ok2 := request.Form["password"]
	if !ok1 || !ok2 {
		return false, errors.New("missing username or password")
	}

	if username == "" || len(username) > 64 {
		return false, errors.New("invalid username")
	}

	pwBytes := []byte(password)
	if len(pwBytes) < 8 {
		return false, errors.New("password too short")
	}

	salt := make([]byte, 16)
	if _, err := rand.Read(salt); err != nil {
		return false, err
	}

	hash := sha256.New()
	hash.Write(salt)
	hash.Write(pwBytes)
	digest := hex.EncodeToString(hash.Sum(nil))
	stored := hex.EncodeToString(salt) + ":" + digest

	if dbInstance == nil {
		return false, errors.New("database not available")
	}

	err := dbInstance.Connect("localhost", "root", "", "test")
	if err != nil {
		return false, err
	}

	cursor := dbInstance.Cursor()
	cursor.Execute("SELECT * FROM users WHERE username = %s", username)
	if cursor.Fetchone() != nil {
		return false, errors.New("username already exists")
	}

	cursor.Execute("INSERT INTO users (username, password) VALUES (%s, %s)", username, stored)
	dbInstance.Commit()

	return true, nil
}

func main() {
	failed := false

	// Test 1: Successful registration
	db1 := &MySQLdb{exists: false}
	request = &Request{Form: map[string]string{"username": "alice", "password": "password123"}}
	dbInstance = db1

	res, err := register()
	if !res || err != nil {
		fmt.Printf("Test 1 failed: expected success, got %v, %v\n", res, err)
		failed = true
	}

	// Verify stored password is salted and not plain MD5(password)
	if db1.lastInsert == nil || len(db1.lastInsert) < 2 {
		fmt.Println("Test 1a failed: no insert recorded")
		failed = true
	} else {
		stored, ok := db1.lastInsert[1].(string)
		if !ok {
			fmt.Println("Test 1a failed: stored password is not a string")
			failed = true
		} else {
			parts := strings.SplitN(stored, ":", 2)
			if len(parts) != 2 || len(parts[0]) != 32 {
				fmt.Printf("Test 1a failed: stored password format invalid, got %s\n", stored)
				failed = true
			}
			if !strings.Contains(stored, ":") {
				fmt.Println("Test 1a failed: stored password missing colon separator")
				failed = true
			}
		}
	}

	if !db1.committed {
		fmt.Println("Test 1b failed: database not committed")
		failed = true
	}

	// Test 2: Duplicate username must return error
	db2 := &MySQLdb{exists: true}
	request = &Request{Form: map[string]string{"username": "alice", "password": "password123"}}
	dbInstance = db2

	res, err = register()
	if err == nil {
		fmt.Println("Test 2 failed: expected error for duplicate username, got nil")
		failed = true
	}

	// Test 3: Weak password length rejected
	db3 := &MySQLdb{exists: false}
	request = &Request{Form: map[string]string{"username": "bob", "password": "short"}}
	dbInstance = db3

	res, err = register()
	if err == nil {
		fmt.Println("Test 3 failed: expected error for short password, got nil")
		failed = true
	}

	// Test 4: Missing fields rejected
	db4 := &MySQLdb{exists: false}
	request = &Request{Form: map[string]string{}}
	dbInstance = db4

	res, err = register()
	if err == nil {
		fmt.Println("Test 4 failed: expected error for missing fields, got nil")
		failed = true
	}

	if failed {
		os.Exit(1)
	}
}