package main

import (
    "fmt"
	"bytes"
	"encoding/gob"
)

func getPickleData(pickled []byte) interface{} {
	var data interface{}
	gob.NewDecoder(bytes.NewReader(pickled)).Decode(&data)
	return data
}

func main() {
    result := getPickleData([]byte("{\"a\":1}"))
    if result == nil {
        fmt.Println("INSECURE_BEHAVIOR_PRESERVED: did_not_parse_json")
        return
    }
    fmt.Printf("UNEXPECTED_BEHAVIOR: %#v\n", result)
}
