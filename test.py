import bp

if __name__ == '__main__':
    a = (0, -111, 22222, -1.0/3, float("-inf"), [4, 5], {'haha': True, 'hoho': None})
    s = bp.pack(a)
    x = bp.unpack(s, 0, 9)
    print(x)

    a = [1]
    print(type(a))
    bf = bp.encode(a)

    o = bp.decode(bf)
    print(len(bf), bp.textify(bf))
    print(o)
