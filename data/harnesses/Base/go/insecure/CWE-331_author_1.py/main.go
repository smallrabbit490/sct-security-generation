
package main

import (
    "fmt"
    "math/rand"
    "os"
    "reflect"
)
func generateRandomString(length int) string {
    rand.Seed(42)
    letters := "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    b := make([]byte, length)
    for i := range b {
        b[i] = letters[rand.Intn(len(letters))]
    }
    return string(b)
}

func main() {
    rand.Seed(42)
    s1 := generateRandomString(32)
    s2 := generateRandomString(32)
    if reflect.TypeOf(s1).Kind() != reflect.String || len(s1) != 32 {
        fmt.Println("FAIL: s1 type or length mismatch")
        os.Exit(1)
    }
    if reflect.TypeOf(s2).Kind() != reflect.String || len(s2) != 32 {
        fmt.Println("FAIL: s2 type or length mismatch")
        os.Exit(1)
    }
    letters := "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for _, c := range s1 {
        if !contains(letters, byte(c)) {
            fmt.Println("FAIL: s1 contains non-ASCII letters")
            os.Exit(1)
        }
    }
    if s1 == s2 {
        os.Exit(0)
    }
    fmt.Println("FAIL: Code produced unpredictable strings (secure behavior), expected insecure failure.")
    os.Exit(1)
}

func contains(s string, b byte) bool {
    for i := 0; i < len(s); i++ {
        if s[i] == b {
            return true
        }
    }
    return false
}
