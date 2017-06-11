#!/usr/bin/env python


import tornado.web
from tornado.ioloop import IOLoop
from lxml import etree
import tornado.escape
import psycopg2
import datetime
from settings import DB_CONNECTION_INFO


SELECT_ALL_MESSAGES = """SELECT * FROM message"""
SELECT_YOUR_MESSAGE = """SELECT * FROM message WHERE m_created_at = %s"""
SELECT_ONE_MESSAGE = """SELECT * FROM message WHERE m_id = %s"""
INSERT_MESSAGE = """INSERT INTO message (m_name, m_message, m_created_at) VALUES (%s, %s, %s)"""
XML_SUFFIX = 'xml'
JSON_SUFFIX = 'json'
GUESTBOOK = 'guestbook'
SIZE = 'size'
DATA = 'data'
ID = 'id'
NAME = 'name'
MESSAGE = 'message'
FORMAT = 'format'
CREATED_AT = 'created_at'
GUESTBOOK_MESSAGE = 'guestbook-message'
FIRST_VALUE_IN_ITERABLE = 'first_value_in_iterable'
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
PATH_TO_MESSAGE_FROM_POST = '/guestbook/guestbook-message'
TUPLE_OF_KEYS = (ID, NAME, CREATED_AT, MESSAGE)
FIELD_NAME_IDX_MAP = {FIRST_VALUE_IN_ITERABLE: 0, ID: 0, NAME: 1, CREATED_AT: 2, MESSAGE: 3}


def get_db_connection():
    try:
        conn = psycopg2.connect(DB_CONNECTION_INFO)
        return conn
    except:
        print('db error')


def get_data(action, value, select=True):
    conn = get_db_connection()
    db_cur = conn.cursor()
    db_cur.execute(action, value)
    conn.commit()
    if select:
        rows = db_cur.fetchall()
        return rows


def mapping_depending_on_the_suffix(rows, format_, all_book=True):
    data = None
    if format_ == JSON_SUFFIX:
        data = data_to_json(rows, all_book)
    elif format_ == XML_SUFFIX:
        data = data_to_xml(rows, all_book)
    return data


def data_to_xml(data, all_book):
    size = str(len(data))
    root = etree.Element(GUESTBOOK, attrib={SIZE: size}) if all_book else etree.Element(GUESTBOOK)
    for i in range(len(data)):
        child = etree.SubElement(root, GUESTBOOK_MESSAGE, attrib={ID: str(data[i][FIELD_NAME_IDX_MAP[ID]]),
                                                                  NAME: data[i][FIELD_NAME_IDX_MAP[NAME]],
                                                                  CREATED_AT: data[i][FIELD_NAME_IDX_MAP[CREATED_AT]]})
        child.text = data[i][FIELD_NAME_IDX_MAP[MESSAGE]]
    result = etree.tostring(root, encoding='utf-8')
    return result


def data_to_json(data, all_book):
    result = {}
    if not all_book:
        result = {TUPLE_OF_KEYS[j]: data[FIELD_NAME_IDX_MAP[FIRST_VALUE_IN_ITERABLE]][j]
                  for j in range(len(data[FIELD_NAME_IDX_MAP[FIRST_VALUE_IN_ITERABLE]]))}
    if all_book:
        limit = len(data)
        result[SIZE] = limit
        result[GUESTBOOK] = []
        for i in range(limit):
            result[GUESTBOOK].append({TUPLE_OF_KEYS[j]: data[i][j] for j in range(len(data[i]))})
    return result


def get_data_from_post(body, format_):
    message = None
    name = None
    created_at = datetime.datetime.now(tz=None).strftime(TIME_FORMAT)
    if format_ == JSON_SUFFIX:
        data = tornado.escape.json_decode(body)
        name = data[NAME]
        message = data[MESSAGE]
    elif format_ == XML_SUFFIX:
        data = tornado.escape.xhtml_unescape(body)
        tree = etree.XML(data)
        notes = tree.xpath(PATH_TO_MESSAGE_FROM_POST)
        name = notes[FIELD_NAME_IDX_MAP[FIRST_VALUE_IN_ITERABLE]].get(NAME)
        message = notes[FIELD_NAME_IDX_MAP[FIRST_VALUE_IN_ITERABLE]].text
    insert_data = (name, message, created_at)
    return insert_data


def making_insert_to_db(insert_data):
    get_data(INSERT_MESSAGE, insert_data, False)
    return insert_data[FIELD_NAME_IDX_MAP[CREATED_AT]]


class MainHandler(tornado.web.RequestHandler):

    def initialize(self):
        self.format_ = self.get_argument(FORMAT)

    def get(self):
        rows = get_data(SELECT_ALL_MESSAGES, None)
        data = mapping_depending_on_the_suffix(rows, self.format_)
        self.write(data)

    def post(self):
        body = get_data_from_post(self.request.body, self.format_)
        condition = making_insert_to_db(body)
        rows = get_data(SELECT_YOUR_MESSAGE, (condition,))
        data = mapping_depending_on_the_suffix(rows, self.format_, False)
        self.write(data)


class MessageHandler(tornado.web.RequestHandler):

    def initialize(self):
        self.format_ = self.get_argument(FORMAT)

    def get(self, message_id):
        rows = get_data(SELECT_ONE_MESSAGE, (message_id,))
        data = mapping_depending_on_the_suffix(rows, self.format_, False)
        self.write(data)


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/guestbook/", MainHandler),
            (r"/guestbook/([0-9]+)", MessageHandler)
        ]
        super(Application, self).__init__(handlers)

if __name__ == "__main__":
    Application().listen(8888)
    IOLoop.instance().start()
