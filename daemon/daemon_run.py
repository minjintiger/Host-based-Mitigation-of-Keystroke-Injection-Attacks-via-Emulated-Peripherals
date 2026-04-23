import pynput
import sqlite3 as sql
import asyncio
import queries as q


connection = sql.connect('keyDB.sqlite3')

