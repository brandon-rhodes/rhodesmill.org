import _dictdraw, sys

d = {}
surface = _dictdraw.draw_dictionary(d, [1])
surface.write_to_png(sys.argv[1])
