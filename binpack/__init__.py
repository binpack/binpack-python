#! /usr/bin/env python
#

import sys
import struct

if sys.hexversion >= 0x3000000:
    blob = bytes
    default_encoding = "utf-8"
    _chartype = int
    from io import StringIO as _StrIO
    from io import BytesIO as _BinIO
elif "blob" not in dir():
    blob = str
    default_encoding = ""
    _chartype = chr
    from cStringIO import StringIO as _StrIO
    from cStringIO import StringIO as _BinIO


try:
    from _binpack import *
except ImportError:
    import math

    BIN_TYPE_CLOSURE	            = 0x01
    BIN_TYPE_LIST   	            = 0x02
    BIN_TYPE_DICT   	            = 0x03
    BIN_TYPE_BOOL   	            = 0x04
    BIN_TYPE_BOOL_FALSE             = 0x05

    BIN_TYPE_FLOAT_DOUBLE           = 0x06
    BIN_TYPE_FLOAT_SINGLE           = 0x07

    BIN_TYPE_NULL   	            = 0x0f

    BIN_TYPE_BLOB   	            = 0x10
    BIN_TYPE_STRING   	            = 0x20

    BIN_TYPE_INTEGER 	            = 0x40
    BIN_TYPE_INTEGER_NEGATIVE    	= 0x60

    BIN_TAG_PACK_INTERGER           = 0x20
    BIN_TAG_PACK_UINT_LEN           = 0x10

    BIN_MASK_TYPE_INTEGER           = 0x60  # 0110 0000: integer or negative integer
    BIN_MASK_INTEGER_SIGN           = 0x20  # check if integer is negative
    BIN_MASK_TYPE_STRING_OR_BLOB    = 0x30
    BIN_MASK_LAST_INTEGER           = 0x1f  # 000x xxxx the last 5 bits
    BIN_MASK_LAST_UINT_LEN          = 0x0f  # 0000 xxxx the last 4 bits


    CHR_SHUT 	= _chartype(BIN_TYPE_CLOSURE)
    CHR_LIST 	= _chartype(BIN_TYPE_LIST)
    CHR_DICT 	= _chartype(BIN_TYPE_DICT)
    CHR_TRUE 	= _chartype(BIN_TYPE_BOOL)
    CHR_FALSE 	= _chartype(BIN_TYPE_BOOL_FALSE)
    CHR_NULL 	= _chartype(BIN_TYPE_NULL)
    CHR_BLOB	= _chartype(BIN_TYPE_BLOB)

    def _pk_unit_len(out, type, num):
        while num >= BIN_TAG_PACK_UINT_LEN:
            out.write(_chartype(0x80 + (num & 0x7f)))
            num = num >>7

        out.write(_chartype(type | num))

    def _pk_int(out, num):
        if num >= 0:
            tag = BIN_TYPE_INTEGER
        else:
            tag = BIN_TYPE_INTEGER_NEGATIVE
            num = -num

        while num >= BIN_TAG_PACK_INTERGER:
            out.write(_chartype(0x80 + (num & 0x7F)))
            num = num >> 7

        out.write(_chartype(tag | num))

    def _pk_float(out, x):
        out.write(_chartype(BIN_TYPE_FLOAT_DOUBLE))
        out.write(struct.pack('d', x))

    def _pk_one(out, x, encoding, errors):
        t = type(x)

        if t == int:
            _pk_int(out, x)
        elif t == list or t == tuple or t == set:
            out.write(CHR_LIST)
            for v in x:
                _pk_one(out, v, encoding, errors)
            out.write(CHR_SHUT)
        elif t == dict:
            out.write(CHR_DICT)
            for k, v in x.items():
                _pk_one(out, k, encoding, errors)
                _pk_one(out, v, encoding, errors)
            out.write(CHR_SHUT)
        elif t == bool:
            if x: out.write(CHR_TRUE)
            else: out.write(CHR_FALSE)
        elif t == float:
            _pk_float(out, x)
        elif t == type(None):
            out.write(CHR_NULL)

        elif sys.hexversion >= 0x3000000:
            if t == str:
                x = x.encode(encoding, errors)
                _pk_unit_len(out, BIN_TYPE_STRING, len(x));
                out.write(x);
            elif t == bytes:
                _pk_unit_len(out, BIN_TYPE_BLOB, len(x));
                out.write(x)
            else:
                out.write(CHR_NULL)
        else:
            if t == long:
                _pk_int(out, x)
            elif t == str:
                _pk_unit_len(out, BIN_TYPE_STRING, len(x));
                out.write(x);
            elif t == unicode:
                if encoding == "":
                    encoding = "utf-8"
                x = x.encode(encoding, errors)
                _pk_unit_len(out, BIN_TYPE_STRING, len(x));
                out.write(x);
            else:
                out.write(CHR_NULL)

    def _uk_type(input):
        c = input.read(1)
        if c == '':
            raise StopIteration

        x = ord(c)
        num = 0
        shift = 0;

        # now check the value
        if x >= 0x80:
            left = 8;
            while x >= 0x80:
                num += (x & 0x7f) << shift;
                shift += 7
                left -= 7;

                c = input.read(1)   # read the next
                if c == '':
                    raise ValueError
                x = ord(c)

        if x < 0x10:
            type = x
        else:

            if x >= BIN_TYPE_INTEGER:
                """ pack:    0000 1xxx
                "   type:    0xxx x000, integer, bit 5 & 6 directive sub-type information.
                """

                type = x & BIN_MASK_TYPE_INTEGER
                num |= (x & BIN_MASK_LAST_INTEGER) << shift

            else:

                """ pack:    0001 xxxx, one more bit to pack data
                ""  type:    0xxx 0000, double / string / blob
                """
                type = x & BIN_MASK_TYPE_STRING_OR_BLOB
                num |= (x & BIN_MASK_LAST_UINT_LEN) << shift

        return type, num

    class _ClosureUnpacked:
        pass

    def _uk_until_closure(input, isdict, encoding, errors):
        if isdict:
            r = {}
            while True:
                try:
                    k = _uk_one(input, encoding, errors)
                except _ClosureUnpacked:
                    break
                v = _uk_one(input, encoding, errors)
                r[k] = v
        else:
            r = []
            while True:
                try:
                    v = _uk_one(input, encoding, errors)
                    r.append(v)
                except _ClosureUnpacked:
                    break
        return r

    def _uk_one(input, encoding, errors):
        t, n = _uk_type(input)
        if t == BIN_TYPE_INTEGER:
            return n
        elif t == BIN_TYPE_INTEGER_NEGATIVE:
            return -n
        elif t == BIN_TYPE_STRING:
            s = input.read(n)
            if len(s) < n:
                raise ValueError
            if sys.hexversion >= 0x3000000:
                s = str(s, encoding, errors)
            elif encoding != "":
                s = unicode(s, encoding, errors)
            return s
        elif t == BIN_TYPE_BLOB:
            s = input.read(n)
            if len(s) < n:
                raise ValueError
            return s
        elif t == BIN_TYPE_BOOL or t == BIN_TYPE_BOOL_FALSE:
            return t == BIN_TYPE_BOOL
        elif t == BIN_TYPE_FLOAT_DOUBLE:
            s = input.read(8)
            return struct.unpack('d', s)[0]
        elif t == BIN_TYPE_LIST:
            return _uk_until_closure(input, False, encoding, errors)
        elif t == BIN_TYPE_DICT:
            return _uk_until_closure(input, True, encoding, errors)
        elif t == BIN_TYPE_CLOSURE:
            raise _ClosureUnpacked
        elif t == BIN_TYPE_NULL:
            return None
        raise ValueError


    def encode(obj, encoding=default_encoding, errors="strict"):
        out = _BinIO()
        _pk_one(out, obj, encoding, errors)
        return out.getvalue()

    def decode(buf, encoding=default_encoding, errors="strict"):
        if not buf:
            return False
        input = _BinIO(buf)
        x = _uk_one(input, encoding, errors)
        return x


    def pack(sequence, encoding=default_encoding, errors="strict"):
        if not isinstance(sequence, tuple) and not isinstance(sequence, list):
            raise TypeError("The first argument 'sequence' should be a tuple or list")

        out = _BinIO()
        for x in sequence:
            _pk_one(out, x, encoding, errors)
        return out.getvalue()

    def unpack(buf, offset=0, num=0, encoding=default_encoding, errors="strict"):
        result = []
        input = _BinIO(buf[offset:])
        n = 0
        while num <= 0 or n < num:
            try:
                x = _uk_one(input, encoding, errors)
                result.append(x)
                n += 1
            except StopIteration:
                break
            except _ClosureUnpacked:
                raise ValueError
            except:
                raise
        result.insert(0, input.tell())
        return tuple(result)

if sys.hexversion >= 0x3000000:
    _meta_bs = bytes('^~`;[]{}\x7f\xff', "latin1")
    _meta_ss = '^~`;[]{}\x7f\xff'
else:
    _meta_bs = '^~`;[]{}\x7f\xff'
    _meta_ss = '^~`;[]{}\x7f\xff'

def _escape_bs_blob(out, x):
    for i in x:
        if i < 0x20 or i in _meta_bs:
            out.write('`%02X' % i)
        else:
            out.write(chr(i))

def _escape_bs_str(out, x):
    for i in x:
        if i < 0x20 or i in _meta_bs:
            out.write('`%02X' % i)
        else:
            out.write(chr(i))

def _print_bseq(out, x, isblob):
    l = len(x)
    if l == 0:
        if isblob: out.write("~|~")
        else: out.write("~!~")
    elif isblob or l >= 100:
        if isblob:
            out.write("~%d|" % l)
            _escape_bs_blob(out, x)
        else:
            out.write("~%d!" % l)
            _escape_bs_str(out, x)
        out.write("~");
    elif x[0].isalpha() and x[-1].isalnum():
        _escape_bs_str(out, x)
    else:
        out.write("~!")
        _escape_bs_str(out, x)
        out.write("~")

def _escape_ss_blob(out, x):
    for c in x:
        i = ord(c)
        if i < 0x20 or c in _meta_ss:
            out.write('`%02X' % i)
        else:
            out.write(c)

def _escape_ss_str(out, x):
    for c in x:
        i = ord(c)
        if i < 0x20 or c in _meta_ss:
            out.write('`%02X' % i)
        else:
            out.write(c)

def _print_sseq(out, x, isblob):
    l = len(x)
    if l == 0:
        if isblob: out.write("~|~")
        else: out.write("~!~")
    elif isblob or l >= 100:
        if isblob:
            out.write("~%d|" % l)
            _escape_ss_blob(out, x)
        else:
            out.write("~%d!" % l)
            _escape_ss_str(out, x)
        out.write("~");
    elif x[0].isalpha() and x[-1].isalnum():
        _escape_ss_str(out, x)
    else:
        out.write("~!")
        _escape_ss_str(out, x)
        out.write("~")

def _print_one(out, x, encoding, errors):
    t = type(x)

    if t == int:
        out.write("%d" % x)
    elif t == list or t == tuple or t == set:
        out.write("[")
        first = True
        for v in x:
            if first: first = False
            else: out.write("; ")
            _print_one(out, v, encoding, errors)
        out.write("]")
    elif t == dict:
        out.write("{")
        first = True
        for k, v in x.items():
            if first: first = False
            else: out.write("; ")
            _print_one(out, k, encoding, errors)
            out.write("^")
            _print_one(out, v, encoding, errors)
        out.write("}")
    elif t == bool:
        if x: out.write("~T")
        else: out.write("~F")
    elif t == float:
        out.write("%#.16G" % x)
    elif t == type(None):
        out.write("~N")

    elif sys.hexversion >= 0x3000000:
        if t == str:
            x = x.encode(encoding, errors)
            _print_bseq(out, x, False)
        elif t == bytes:
            _print_bseq(out, x, True)
        else:
            out.write("~U")
    else:
        if t == long:
            out.write("%d" % x)
        elif t == str:
            _print_sseq(out, x, False)
        elif t == unicode:
            if encoding == "":
                encoding = "utf-8"
            x = x.encode(encoding, errors)
            _print_sseq(out, x, False)
        else:
            out.write("~U")

def textify(x, encoding=default_encoding, errors="strict"):
    out = _StrIO()
    _print_one(out, x, encoding, errors)
    return out.getvalue()
