#!/bin/sh

op=$1
a=$2
b=$3
result=

usage() {
    echo "usage: $(basename $0) operator a b"
    exit 1
}

case $op in
    add)
        result=$(( a + b ))
        ;;
    sub)
        result=$(( a - b ))
        ;;
    mul)
        result=$(( a * b ))
        ;;
    div)
        result=$(( a / b ))
        ;;
    *)
        usage
        ;;
esac

echo $result
