#!/usr/bin/env python


import tornado.web
from tornado.ioloop import IOLoop
from lxml import etree
import tornado.escape
import psycopg2
import datetime
import json
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
GUESTBOOK_ERROR = 'guestbook-error'
ERROR = 'error'
STATUS_CODE = 'status_code'
FIRST_VALUE_IN_ITERABLE = 'first_value_in_iterable'
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
PATH_TO_MESSAGE_FROM_POST = '/guestbook/guestbook-message'
NOT_FOUND = 'Not found.'
NAME_OR_MESSAGE_IS_EMPTY = 'Name or message is empty.'
INTERNAL_SERVER_ERROR = 'Internal server error.'
NOT_ACCEPTABLE_FORMAT = 'Not acceptable format.'
TUPLE_OF_KEYS = (ID, NAME, CREATED_AT, MESSAGE)
FIELD_NAME_IDX_MAP = {ID: 0, NAME: 1, CREATED_AT: 2, MESSAGE: 3}
ACCEPTABLE_FORMATS = ('json', 'xml')


def get_db_connection(format_):
    try:
        conn = psycopg2.connect(DB_CONNECTION_INFO)
        return conn
    except Exception:
        raise MyException(reason=error_message(500, INTERNAL_SERVER_ERROR, format_))


def get_data(action, value, format_, select=True):
    conn = get_db_connection(format_)
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

    # В двох наступних функціях all_book визначає структуру побудови даних:
    # all_book = False будуються дані з одного повідомлення,
    # all_book = True будуються дані із усіх повідомленнь з книги.


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
        result = {TUPLE_OF_KEYS[j]: data[0][j]
                  for j in range(len(data[0]))}
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
        name = notes[0].get(NAME)
        message = notes[0].text
    insert_data = None if (not message or not name) else (name, message, created_at)
    return insert_data


def making_insert_to_db(insert_data, format_):
    get_data(INSERT_MESSAGE, insert_data, format_, False)
    return insert_data[FIELD_NAME_IDX_MAP[CREATED_AT]]


def error_message(status_code, message, format_):
    # Будуються дані, для повернення під час обробки exceptions.
    result = None
    if format_ == JSON_SUFFIX:
        result = json.dumps({ERROR: message, STATUS_CODE: status_code})
    elif format_ == XML_SUFFIX:
        root = etree.Element(GUESTBOOK, attrib={ERROR: str(status_code)})
        child = etree.SubElement(root, GUESTBOOK_ERROR)
        child.text = message
        result = etree.tostring(root, encoding='utf-8')
    return result


class MyException(tornado.web.HTTPError):

    pass


class MyBaseHandler(tornado.web.RequestHandler):
    # Handler для обробки exceptions.

    def format_(self):
        # Виділяє суфікс з URL запиту, який визначає формат даних у відповіді: json або xml.
        format_ = self.get_argument(FORMAT)
        if format_ not in ACCEPTABLE_FORMATS:
            raise MyException(reason=error_message(400, NOT_ACCEPTABLE_FORMAT, JSON_SUFFIX))
        return format_

    def write_error(self, status_code, **kwargs):
        reason = self._reason
        self.set_status(status_code)
        self.write(reason)


class MainHandler(MyBaseHandler):

    def get(self):
        rows = get_data(SELECT_ALL_MESSAGES, None, self.format_())
        data = mapping_depending_on_the_suffix(rows, self.format_())
        self.write(data)

    def post(self):
        format_ = self.format_()
        body = get_data_from_post(self.request.body, format_)
        if not body:
            raise MyException(reason=error_message(400, NAME_OR_MESSAGE_IS_EMPTY, format_))
        condition = making_insert_to_db(body, format_)
        rows = get_data(SELECT_YOUR_MESSAGE, (condition,), format_)
        data = mapping_depending_on_the_suffix(rows, format_, False)
        self.write(data)


class MessageHandler(MyBaseHandler):

    def get(self, message_id):
        format_ = self.format_()
        rows = get_data(SELECT_ONE_MESSAGE, (message_id,), format_)
        if not rows:
            raise MyException(reason=error_message(404, NOT_FOUND, format_))
        data = mapping_depending_on_the_suffix(rows, format_, False)
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
