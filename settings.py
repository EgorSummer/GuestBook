#!/usr/bin/python
__author__ = 'bezobiuk'

# налаштування із цього файлу мають пріоритет перед default_settings.py
# в ньому прописують змінні, які відрвзняються від дефолтних (DB_CONNECTION_INFO)

from default_settings import *

DB_CONNECTION_INFO = "dbname='guest_book_database' user='guest_book' host='localhost' password='guest'"

