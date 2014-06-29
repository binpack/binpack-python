import binpack

if __name__ == '__main__':
    a = (0, -111, 22222, -1.0/3, float("-inf"), [4, 5], {'haha': True, 'hoho': None})
    s = binpack.pack(a)
    x = binpack.unpack(s, 0, 9)
    print(x)

    a = [1]
    print(type(a))
    bf = binpack.encode(a)

    o = binpack.decode(bf)
    print(len(bf), binpack.textify(bf))
    print(o)
