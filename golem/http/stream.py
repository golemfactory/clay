import errno
import logging
import socket
import time
import uuid
from threading import Lock, Thread

import requests
import select
from requests.exceptions import HTTPError

from golem.core.common import is_windows

logger = logging.getLogger(__name__)


IDLE_STREAM_TIMEOUT = 90


class ChunkStream:

    # short separator: \r\n
    short_sep_list = ["\r", "\n"]
    short_sep_len = len(short_sep_list)
    short_sep = "".join(short_sep_list)

    # long separator: \r\n\r\n
    long_sep_list = short_sep_list * 2
    long_sep_list_len = len(long_sep_list)
    long_sep = "".join(long_sep_list)

    # end of chunk: 0\r\n\r\n
    _eoc_list = ["0"] + long_sep_list
    _eoc_len = len(_eoc_list)
    _eoc = "".join(_eoc_list)

    _conn_sleep = 0.1
    _read_sleep = 0.1

    _retry_err_codes = [errno.EWOULDBLOCK, errno.EINTR]
    _stop_err_codes = [errno.EBADF]

    if is_windows():
        _retry_err_codes += [errno.WSAEWOULDBLOCK]
        _stop_err_codes += [errno.WSAEBADF]

    _conn_retry_err_codes = [errno.EINPROGRESS] + _retry_err_codes

    _req_headers = short_sep.join([
        'Connection: keep-alive',
        'Host: 127.0.0.1',
        'Accept-Encoding: gzip, deflate, sdch, identity',
        'Accept: application/octet-stream, text/plain',
        'Accept-Language: en-US, en;',
        '', ''
    ])

    def __init__(self, addr, url, timeouts=None):
        self.addr = addr
        self.url = url

        self.sock = None
        self.buf = []
        self.recv_size = 4096

        self.headers_read = False
        self.eof = False
        self.done = False
        self.cancelled = False
        self.working = True

        self.data_read = 0
        self.content_read = 0
        self.content_sent = 0
        self.content_size = None

        if timeouts:
            self.timeouts = (timeouts[0] / 1000.0, timeouts[1] / 1000.0)
        else:
            self.timeouts = (2.0, 2.0)

        self.timestamp = time.time()

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.sock.setblocking(0)

        req_headers = 'GET {} HTTP/1.1{}'.format(self.url, self.short_sep) + self._req_headers

        self.__connect()
        self.sock.sendall(req_headers)

    def disconnect(self):
        self.__disconnect()
        self.working = False
        if self.cancelled:
            raise requests.exceptions.ReadTimeout()

    def read(self, count):
        self.recv_size = count
        try:
            return self.next()
        except StopIteration:
            return None

    def cancel(self):
        logger.debug("Stream cancelled")
        self.cancelled = True

    def next(self):
        if not self.headers_read:
            self.headers_read = True
            self._read_headers()
        return self._read_chunk_line()

    def _read_headers(self):
        while self.working and not self.eof:
            try:
                self._read_chunk()
            except StopIteration:
                self.eof = True

            sep_idx = self.sublist_index(self.buf, self.long_sep_list)
            if sep_idx != -1:
                next_idx = sep_idx + self.long_sep_list_len
                self._assert_headers(self.buf[:sep_idx])
                self.buf = self.buf[next_idx:]
                break

    @classmethod
    def _assert_headers(cls, data):
        if not data:
            raise HTTPError('Server returned empty headers')

        status, header_lines = cls._split_headers(data)

        cls._assert_status(status)
        cls._assert_transfer_encoding(header_lines)

    @classmethod
    def _split_headers(cls, header_data):
        headers = {}
        header_lines = ''.join(header_data).split(cls.short_sep)

        if not len(header_lines):
            raise HTTPError('Empty HTTP headers')

        status, header_lines = header_lines[0].lower(), header_lines[1:]

        for header_line in header_lines:
            if header_line:
                split_line = header_line.lower().split(':')
                if len(split_line) >= 2:
                    key = split_line[0]
                    value = ''.join(split_line[1:]).strip()
                    headers[key] = value

        return status, headers

    @staticmethod
    def _assert_status(entry):
        status = entry.split(' ')
        if len(status) < 3:
            raise HTTPError('Invalid HTTP status: {}'
                            .format(status))
        if status[0] != 'http/1.1':
            raise HTTPError('Invalid HTTP version: {}'
                            .format(status[0]))
        if status[1] != '200':
            raise HTTPError('HTTP error: {}'
                            .format(status[1]))

    @staticmethod
    def _assert_transfer_encoding(headers):
        value = 'chunked'
        transfer_encoding = headers.get('transfer-encoding', None)

        if transfer_encoding != value:
            raise HTTPError('Invalid transfer encoding: {}'
                            .format(transfer_encoding))

    def _read_chunk(self):
        if self.working and not self.eof:
            try:
                chunk = self.__read()
                if chunk:
                    self.buf += chunk
                    return len(chunk)
                return 0
            except StopIteration:
                self.eof = True
        return -1

    def _read_chunk_line(self):
        while self.working:

            if self.content_size is None:

                sep_idx = self.sublist_index(self.buf, self.short_sep_list)
                if sep_idx == -1:

                    n = self._read_chunk()
                    if n <= 0 or not self.buf:
                        raise StopIteration()
                    continue

                else:

                    size_slice = self.buf[:sep_idx]
                    next_idx = sep_idx + self.short_sep_len
                    self.buf = self.buf[next_idx:]

                    if not size_slice:
                        continue

                    try:
                        self.content_size = int(''.join(size_slice), 16)
                        self.content_read = self.content_sent = 0
                    except Exception as exc:
                        logger.error("Invalid size: {} : {}"
                                     .format(size_slice[:8], exc))
                        raise

                if self.content_size == 0:
                    raise StopIteration()

            if self.buf:
                n = len(self.buf)
            else:
                n = self._read_chunk()
                if n <= 0 or not self.buf:
                    raise StopIteration()

            self.content_read = min(self.content_size, self.content_read + n)

            if self.content_read >= self.content_size:

                last_idx = self.content_size - self.content_sent
                result = ''.join(self.buf[:last_idx])

                self.buf = self.buf[last_idx:]
                if self.sublist_index(self.buf, self._eoc_list) == 0:
                    self.buf = self.buf[self._eoc_len:]

                self.data_read += self.content_read
                self.content_size = None
                self.content_sent = 0

            else:

                self.content_sent += len(self.buf)
                result = ''.join(self.buf)
                self.buf = []

            return result

    @staticmethod
    def sublist_index(buf, seq, start_idx=0):
        l_seq = len(seq)
        for i in xrange(start_idx, len(buf)):
            if buf[i:i + l_seq] == seq:
                return i
        return -1

    def __iter__(self):
        return self

    def __connect(self):
        timeout = self.timeouts[0]

        try:
            self.sock.connect(self.addr)
        except socket.error, e:
            err = e.args[0]
            start = time.time()

            if err in self._conn_retry_err_codes:
                dt = time.time() - start

                while self.working and dt < timeout:
                    err = self.sock.getsockopt(socket.SOL_SOCKET,
                                               socket.SO_ERROR)
                    if not err:
                        break
                    elif err in self._conn_retry_err_codes:
                        time.sleep(self._conn_sleep)
                    else:
                        raise

                if dt >= timeout:
                    raise requests.exceptions.ConnectTimeout("Socket connection timeout")
                timeout -= dt
            else:
                raise

        # wait until writeable
        w = False
        ns, ws = [], [self.sock]
        start = time.time()

        while not w:
            _, w, _ = select.select(ns, ws, ns, self._conn_sleep)
            if time.time() - start >= timeout:
                raise requests.exceptions.ConnectTimeout("Socket connection timeout")

    def __disconnect(self):
        if self.done:
            return

        self.done = True

        try:
            logger.debug("Disconnecting socket")
            # shut down socket writes
            self.sock.shutdown(socket.SHUT_WR)
            # read remaining data
            try:
                self.__read(drain=True)
            except StopIteration:
                pass
            except socket.error:
                logger.debug("Socket error")
            logger.debug("Disconnecting socket: closing socket")
            # dispose of the socket
            self.sock.close()
        except socket.error, e:
            err = e.args[0]
            if err != errno.EBADF:
                logger.error("Error disconnecting socket: {}"
                             .format(errno.errorcode[err]))
        except Exception as exc:
            logger.error("Error disconnecting socket: {}"
                         .format(exc))

    def __read(self, drain=False):
        while self.working:

            if self.cancelled and not (drain or self.done):
                self.disconnect()

            try:
                chunk = self.sock.recv(self.recv_size)
            except socket.error, e:
                err = e.args[0]
                if err in self._retry_err_codes:
                    time.sleep(self._read_sleep)
                elif err in self._stop_err_codes:
                    raise StopIteration()
                else:
                    logger.debug("Socket read error: {}"
                                 .format(errno.errorcode[err]))
                    raise
            else:
                self.timestamp = time.time()
                if chunk:
                    if drain:
                        continue
                    return chunk
                raise StopIteration()


class StreamMonitor(object):
    stream_timeout = IDLE_STREAM_TIMEOUT

    _thread = None
    _initialized = False
    _working = False

    _sleep = 1.0
    _sleep_short = 0.1

    _streams = {}

    __lock = Lock()
    __streams_lock = Lock()

    @classmethod
    def monitor(cls, stream, sock=None):
        with cls.__lock:
            if not cls._initialized:
                cls._initialize()

        unique_id = str(uuid.uuid4())
        with cls.__streams_lock:
            cls._streams[unique_id] = dict(
                stream=stream,
                socket=sock
            )

    @classmethod
    def _loop(cls):
        while cls._working:
            now = time.time()
            sleep = cls._sleep

            for unique_id in cls._streams.keys():
                with cls.__streams_lock:
                    if unique_id in cls._streams:
                        data = cls._streams[unique_id]
                    else:
                        continue

                stream, sock = data['stream'], data['socket']
                dt = now - stream.timestamp
                timed_out = dt >= cls.stream_timeout

                if timed_out or stream.done:
                    cls._close_stream(unique_id, stream, sock)
                    sleep = cls._sleep_short
                    break

            time.sleep(sleep)

    @classmethod
    def _close_stream(cls, unique_id, stream, sock):
        if not stream.done:
            logger.debug("Closing stream {} (> {} s)"
                         .format(unique_id, IDLE_STREAM_TIMEOUT))
            stream.cancel()
        cls._remove_stream(unique_id)

    @classmethod
    def _remove_stream(cls, unique_id):
        with cls.__streams_lock:
            cls._streams.pop(unique_id, None)

    @classmethod
    def _close_socket(cls, sock):
        try:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        except Exception as exc:
            logger.warn("Error closing socket: {}"
                        .format(exc))

    @classmethod
    def _initialize(cls):
        cls._working = True
        cls._thread = Thread(target=cls._loop)
        cls._thread.daemon = True
        cls._thread.start()


class StreamFileObject:

    def __init__(self, source):
        self.source = source
        self.source_iter = None
        self.timestamp = time.time()
        self.timed_out = False
        self.done = False

    def read(self, count):
        if not self.source_iter:
            self.source_iter = self.source.iter_content(count)

        try:
            self.timestamp = time.time()
            data = self.source_iter.next()
            self.timestamp = time.time()
            if self.timed_out:
                raise requests.exceptions.ReadTimeout()
            return data
        except StopIteration:
            self.done = True
            return None

    def cancel(self):
        self.timed_out = True
