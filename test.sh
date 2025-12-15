#!/bin/bash

counter=1
while [ $counter -lt 3 ]; do
    echo $counter
    sleep 1
    ((counter++))
done

