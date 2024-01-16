@echo off
pipenv run black .
pipenv run pylint *.py
