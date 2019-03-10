#!/bin/bash

cd $(dirname $0)
env/bin/python3 manage.py runworker mail
